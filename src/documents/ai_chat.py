import logging
from typing import Any
from typing import cast

from django.conf import settings
from drf_spectacular.utils import extend_schema
from langchain_community.callbacks.manager import get_openai_callback
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
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


class AnswerResponseSerializer(serializers.Serializer):
    reply = serializers.CharField(help_text="The answer of the AI assistant")
    document_ids = serializers.ListField(
        help_text="The document ids of the documents that are relevant to the question"
    )


@extend_schema(
    description="Ask a question to the AI assistant",
    request=QuestionSerializer,
    responses={200: AnswerResponseSerializer},
)
class QuestionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, format=None) -> Response:
        serializer = QuestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        # After serializer.is_valid() is called, validated_data will have values
        validated_data = cast(dict[str, Any], serializer.validated_data)
        question = validated_data["question"]

        # Log the question for debugging
        logger.info(f"Received question: {question}")

        try:
            # Get answers using RAG
            reply, document_ids = self.get_rag_answers(question)

            return Response({"reply": reply, "document_ids": document_ids})
        except Exception as e:
            logger.error(f"Error generating RAG answer: {e!s}")
            # Return http error code 500
            return Response(
                {
                    "reply": "An error occurred while generating the answer",
                    "document_ids": [],
                },
                status=500,
            )

    def get_rag_answers(self, question: str) -> tuple[str, list[str]]:
        """
        Uses Retrieval Augmented Generation to answer the question.
        Returns a tuple of (reply, document_ids)
        """
        # Initialize the embeddings and vector store
        try:
            embeddings = DocumentEmbeddings()
            vector_store = embeddings.vector_store
        except Exception as e:
            logger.error(f"Error initializing embeddings: {e!s}")
            raise

        # Search for relevant documents in the vector store
        try:
            # Get most relevant documents for the query
            search_results = vector_store.similarity_search(
                question,
                k=3,  # Retrieve top 3 most relevant chunks
            )

            # Extract content from the search results
            context_texts = [doc.page_content for doc in search_results]
            context = "\n\n".join(context_texts)
            document_ids = [
                doc.metadata.get("document_id", "") for doc in search_results
            ]

            logger.info(f"Retrieved {len(context_texts)} relevant document chunks")
        except Exception as e:
            logger.error(f"Error searching vector store: {e!s}")
            context = ""  # Empty context if search fails
            logger.warning("Using empty context due to search failure")

        # Create a prompt for the chat model
        system_template = """You are a helpful assistant for a document management system.
        Answer the user's question based on the following context from their documents.
        If the context doesn't contain relevant information, say so politely and suggest
        what kind of documents might contain the answer. Formulate your answer in the same language as the question.

        Context information:
        {context}
        """

        human_template = "{question}"

        chat_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_template),
                ("human", human_template),
            ]
        )

        # Set up the OpenAI chat model
        api_key = (
            settings.OPENAI_API_KEY.get_secret_value()
            if settings.OPENAI_API_KEY.get_secret_value()
            else None
        )
        if not api_key:
            logger.error("OpenAI API key is not set")
            raise ValueError("OpenAI API key is not set")

        llm = ChatOpenAI(
            model="gpt-4o",  # Using latest model, can be changed to gpt-3.5-turbo for cost savings
            temperature=0,
            api_key=api_key,
        )

        # Set up and run the chain for English response
        chain = chat_prompt | llm | StrOutputParser()

        with get_openai_callback() as cb:
            reply = chain.invoke({"context": context, "question": question})
            logger.info(
                f"OpenAI API usage: {cb.total_tokens} tokens, cost: ${cb.total_cost}"
            )

        return reply, document_ids
