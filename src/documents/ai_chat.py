import logging
import uuid
from typing import Annotated
from typing import Any
from typing import TypedDict
from typing import cast

from django.conf import settings
from drf_spectacular.utils import extend_schema
from langchain_community.callbacks.manager import get_openai_callback
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
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from documents.embeddings import DocumentEmbeddings

logger = logging.getLogger("paperless.ai_chat")


class QuestionSerializer(serializers.Serializer):
    question = serializers.CharField(
        required=True, help_text="The question to ask the AI assistant"
    )
    session_id = serializers.CharField(
        required=False, help_text="Session ID for tracking conversation history"
    )


class ClearHistorySerializer(serializers.Serializer):
    session_id = serializers.CharField(
        required=True, help_text="Session ID for tracking conversation history"
    )


class AnswerResponseSerializer(serializers.Serializer):
    reply = serializers.CharField(help_text="The answer of the AI assistant")
    document_ids = serializers.ListField(
        help_text="The document ids of the documents that are relevant to the question"
    )
    session_id = serializers.CharField(
        help_text="Session ID for tracking conversation history"
    )


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


def create_chat_graph() -> StateGraph:
    """Create the LangGraph chat graph"""

    # Initialize the chat model
    api_key = settings.OPENAI_API_KEY.get_secret_value()
    if not api_key:
        raise ValueError("OpenAI API key is not set")

    llm = ChatOpenAI(
        model="gpt-4",  # Using latest model
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


@extend_schema(
    description="Ask a question to the AI assistant",
    request=QuestionSerializer,
    responses={200: AnswerResponseSerializer},
)
class QuestionView(APIView):
    permission_classes = [IsAuthenticated]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chat_graph = create_chat_graph()

    def post(self, request: Request, format=None) -> Response:
        serializer = QuestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        # Get validated data
        validated_data = cast(dict[str, Any], serializer.validated_data)
        question = validated_data["question"]

        # Get or create session ID
        session_id = validated_data.get("session_id")
        if not session_id:
            session_id = f"chat_{request.user.id}_{uuid.uuid4()}"

        # Get chat history
        history = get_chat_history(session_id)

        try:
            # Create initial state
            initial_state: ChatState = {
                "messages": [*history.messages, HumanMessage(content=question)],
                "context": "",
                "document_ids": [],
            }

            # Run the chat graph
            with get_openai_callback() as cb:
                final_state = self.chat_graph.invoke(initial_state)

                logger.info(
                    f"OpenAI API usage: {cb.total_tokens} tokens, cost: ${cb.total_cost}"
                )

            # Get the last AI message
            last_message = final_state["messages"][-1]
            if not isinstance(last_message, AIMessage):
                raise ValueError("Expected last message to be AI message")

            # Update chat history
            history.add_user_message(question)
            history.add_ai_message(str(last_message.content))

            return Response(
                {
                    "reply": last_message.content,
                    "document_ids": final_state["document_ids"],
                    "session_id": session_id,
                }
            )

        except Exception as e:
            logger.error(f"Error in chat: {e!s}")
            return Response(
                {
                    "reply": "An error occurred while generating the answer",
                    "document_ids": [],
                    "session_id": session_id,
                },
                status=500,
            )


@extend_schema(
    description="Clear the chat history for a session",
    request=ClearHistorySerializer,
    responses={200: {"type": "object", "properties": {"status": {"type": "string"}}}},
)
class ClearChatHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, format=None) -> Response:
        serializer = ClearHistorySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        validated_data = cast(dict[str, Any], serializer.validated_data)
        session_id = validated_data["session_id"]

        try:
            # Get the chat history and clear it
            history = get_chat_history(session_id)
            history.clear()
            logger.info(f"Cleared chat history for session: {session_id}")
            return Response({"status": "success"})

        except Exception as e:
            logger.error(f"Error clearing chat history: {e!s}")
            return Response(
                {"status": "error", "message": "Failed to clear chat history"},
                status=500,
            )
