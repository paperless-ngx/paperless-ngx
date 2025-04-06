import logging
from typing import Annotated
from typing import TypedDict

from django.conf import settings
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage
from langchain_core.messages import BaseMessage
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts import MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langchain_redis import RedisChatMessageHistory
from langgraph.graph import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from documents.embeddings import DocumentEmbeddings

logger = logging.getLogger("paperless.ai_chat")


class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], "The chat messages"]
    context: Annotated[str, "The context from RAG"]
    document_ids: Annotated[list[str], "The document IDs used for context"]


def get_chat_history(session_id: str) -> BaseChatMessageHistory:
    """Get a chat history instance for the given session ID"""
    redis_url = getattr(settings, "EMBEDDING_REDIS_URL", "redis://localhost:6379")
    return RedisChatMessageHistory(
        session_id=session_id,
        redis_url=redis_url,
        key_prefix="paperless_chat:",
        ttl=86400 * 30,  # 30 days TTL
    )


def search_documents(query: str) -> tuple[str, list[str]]:
    """Search for relevant documents using RAG"""
    try:
        embeddings = DocumentEmbeddings()
        vector_store = embeddings.vector_store

        # Get most relevant documents for the query
        search_results = vector_store.similarity_search(
            query,
            k=3,  # Retrieve top 3 most relevant chunks
        )

        # Extract content from the search results
        context_texts = [doc.page_content for doc in search_results]
        context = "\n\n".join(context_texts)

        # Get document IDs
        document_ids = []
        for doc in search_results:
            doc_id = doc.metadata.get("document_id")
            if doc_id:
                document_ids.append(str(doc_id))

        logger.info(f"Retrieved {len(context_texts)} relevant document chunks")
        return context, document_ids

    except Exception as e:
        logger.error(f"Error searching vector store: {e!s}")
        return "", []


def create_chat_graph() -> CompiledStateGraph:
    """Create the LangGraph chat graph"""

    # Initialize the chat model
    api_key = settings.OPENAI_API_KEY.get_secret_value()
    if not api_key:
        raise ValueError("OpenAI API key is not set")

    llm = ChatOpenAI(
        model="gpt-4o-mini",  # Using latest model
        temperature=0,
        api_key=api_key,
    )

    # Create the chat prompt
    system_template = """You are a helpful assistant for a document management system.
    Answer the user's question based on the following context from their documents and the conversation history.
    If the context doesn't contain relevant information, say so politely and suggest
    what kind of documents might contain the answer. Formulate your answer in the same language as the question.
    """

    user_template = """
    Context information:
    {context}

    Question:
    {question}
    """

    chat_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_template),
            MessagesPlaceholder(variable_name="messages"),
            ("human", user_template),
        ]
    )

    # Create the graph
    graph = StateGraph(ChatState)

    # Add nodes
    def rag_node(state: ChatState) -> ChatState:
        """Node that performs RAG search"""
        # Get the last user message
        last_message = state["messages"][-1]
        if not isinstance(last_message, HumanMessage):
            return state

        # Search for relevant documents
        content = str(last_message.content)  # Ensure content is a string
        context, document_ids = search_documents(content)

        return {
            "messages": state["messages"],
            "context": context,
            "document_ids": document_ids,
        }

    def chat_node(state: ChatState) -> ChatState:
        """Node that generates the chat response"""
        # Get the last user message
        last_message = state["messages"][-1]
        if not isinstance(last_message, HumanMessage):
            return state

        # Generate response
        chain = chat_prompt | llm | StrOutputParser()
        response = chain.invoke(
            {
                "messages": state["messages"][:-1],  # Exclude the last message
                "context": state["context"],
                "question": last_message.content,
            }
        )

        # Add the response to messages
        new_messages = state["messages"] + [AIMessage(content=response)]

        return {
            "messages": new_messages,
            "context": state["context"],
            "document_ids": state["document_ids"],
        }

    # Add nodes to graph
    graph.add_node("rag", rag_node)
    graph.add_node("chat", chat_node)

    # Add edges
    graph.add_edge("rag", "chat")
    graph.add_edge("chat", END)

    # Set entry point
    graph.set_entry_point("rag")

    return graph.compile()
