import logging
import random
import traceback
from collections.abc import Sequence
from typing import Annotated
from typing import Any
from typing import TypedDict

from django.conf import settings
from langchain_community.callbacks import get_openai_callback
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
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from documents.embeddings import DocumentEmbeddings
from documents.models import Document

logger = logging.getLogger("paperless.ai_chat")


class ChatState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    context: Annotated[str, "The context from RAG"]
    document_ids: Annotated[list[str], "The document IDs used for context"]


def get_chat_history(session_id: str) -> BaseChatMessageHistory:
    """Get a chat history instance for the given session ID"""
    redis_url = getattr(settings, "EMBEDDING_REDIS_URL")
    if not redis_url:
        logger.error("EMBEDDING_REDIS_URL is not set, AI Chat will not work")
        raise ValueError("EMBEDDING_REDIS_URL is not set")
    logger.info(
        f"Creating RedisChatMessageHistory with URL {redis_url} for session {session_id}"
    )
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
            return_metadata=True,
            return_all=True,
        )

        # Extract content from the search results
        # logger.info(search_results[0])
        context_texts = [doc.page_content for doc in search_results]
        document_ids = [doc.metadata.get("document_id") for doc in search_results]
        documents = [Document.objects.get(pk=id) for id in document_ids]
        context = "\n\n".join(
            str(
                {
                    "title": doc.title,
                    "id": doc.pk,
                    "content": context_text,
                    "link": f"{settings.PAPERLESS_URL}/documents/{doc.pk}/",
                }
            )
            for doc, context_text in zip(documents, context_texts)
        )
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
        traceback.print_exc()
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
    You can use markdown to format your answer.
    Cite the documents in your answer using numbers counting up from one like '[1]'. Place the citations directly after the corresponding information in your answer.
    On the bottom of your answer give a list of references for each document you cited using the following format:
    \n[1]: [title](link)\n
    [2]: [title](link)\n
    [3]: [title](link)\n
    If you don't have any references, don't mention it. If you are citing different chunks from the same document (same id), use the same citation number for each chunk.
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

        return {
            "messages": [AIMessage(content=response)],
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


def process_question(
    question: str, user_id: int, session_id: str | None = None
) -> tuple[str, list[str], str]:
    """
    Process a user question through the chat agent and handle chat history.

    Args:
        question: The user's question
        user_id: The ID of the user asking the question
        session_id: Optional session ID for conversation continuity

    Returns:
        Tuple of (reply, document_ids, session_id)
    """
    # Create chat graph
    chat_graph = create_chat_graph()

    # Get or create session ID
    if not session_id:
        session_id = f"{user_id}_{random.randint(1, 1000000)}"

    # Get chat history
    history = get_chat_history(session_id)
    user_message = HumanMessage(content=question)

    try:
        # Create initial state
        initial_state: ChatState = {
            "messages": [*history.messages, user_message],
            "context": "",
            "document_ids": [],
        }

        # Run the chat graph
        with get_openai_callback() as cb:
            final_state = chat_graph.invoke(initial_state)
            logger.info(
                f"OpenAI API usage: {cb.total_tokens} tokens, cost: ${cb.total_cost}"
            )

        # Get the last AI message
        ai_answer = final_state["messages"][-1]
        if not isinstance(ai_answer, AIMessage):
            raise ValueError("Expected last message to be AI message")

        # Update chat history
        history.add_messages([user_message, ai_answer])

        return str(ai_answer.content), final_state["document_ids"], session_id

    except Exception as e:
        logger.error(f"Error in chat: {type(e)}: {e!s}")
        logger.error(traceback.format_exc())
        return "An error occurred while generating the answer", [], session_id


def clear_chat_history(session_id: str) -> bool:
    """
    Clear the chat history for a specific session.

    Args:
        session_id: The session ID to clear history for

    Returns:
        Boolean indicating success
    """
    logger.info(f"Clearing chat history for session: {session_id}")
    try:
        history = get_chat_history(session_id)
        history.clear()
        logger.info(f"Cleared chat history for session: {session_id}")
        return True
    except Exception as e:
        logger.error(f"Error clearing chat history: {e!s}")
        return False


def get_chat_messages(session_id: str) -> list[dict[str, Any]]:
    """
    Get the formatted chat messages for a specific session.

    Args:
        session_id: The session ID to get messages for

    Returns:
        List of message dictionaries in the format expected by the frontend
    """
    try:
        history = get_chat_history(session_id)
        messages = []

        logger.info(
            f"Found {len(history.messages)} messages in chat history for session: {session_id}"
        )
        for message in history.messages:
            logger.info(f"Message of type {type(message)}: {message.content}")
            if isinstance(message, HumanMessage):
                messages.append(
                    {
                        "text": message.content,
                        "fromUser": True,
                    }
                )
            elif isinstance(message, AIMessage):
                messages.append(
                    {
                        "text": message.content,
                        "fromUser": False,
                    }
                )

        return messages
    except Exception as e:
        logger.error(f"Error getting chat messages: {e!s}")
        logger.error(traceback.format_exc())
        return []
