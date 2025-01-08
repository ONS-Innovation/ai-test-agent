from typing import List, Optional

from flask import Flask, jsonify, request
from google.oauth2 import service_account
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI

app = Flask(__name__)


def load_credentials():
    """Load Google service account credentials from file."""
    credentials = service_account.Credentials.from_service_account_file(
        "service-account.json",
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return credentials


class SurveyAgent:
    def __init__(self):
        credentials = load_credentials()
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-pro",
            google_auth_credentials=credentials,
            temperature=0.7,
        )
        self.messages = []
        self.job_context = None

    def set_job_context(
        self, job_title: str, job_description: str, organization: str
    ) -> None:
        """Set the job context for the agent to use in responses."""
        self.job_context = (
            f"Professional Role Information:\n"
            f"Job Title: {job_title}\n"
            f"Job Description: {job_description}\n"
            f"Organization's Activity: {organization}"
        )
        # Add context as system message
        self.messages = [HumanMessage(content=self.job_context)]

    def _create_open_ended_chain(self):
        """Create a chain for handling open-ended questions."""
        prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="history"),
                (
                    "human",
                    (
                        "Please provide a brief and focused answer to the following "
                        "question based on your professional role and experience. "
                        "Keep your response to 1-2 sentences maximum.\n\n"
                        "Question: {question}"
                    ),
                ),
            ]
        )
        return prompt | self.llm

    def _create_multiple_choice_chain(self, choices: List[str]):
        """Create a chain for handling multiple choice questions."""
        prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="history"),
                (
                    "human",
                    (
                        "STRICT INSTRUCTION: You MUST select and return ONLY ONE of the "
                        "exact options listed below. Do not add any explanation, do not "
                        "modify the text, do not add any other text. If none of the options "
                        "seem perfect, choose 'none of the above' or the closest match. "
                        "Your response must be a VERBATIM COPY of one of the options "
                        "(without the number prefix).\n\n"
                        "Available choices:\n"
                        "{choices}\n\n"
                        "Question: {question}\n\n"
                        "Select exactly one option from above (without the number):"
                    ),
                ),
            ]
        )
        return prompt | self.llm

    def ask_question(self, question: str, choices: Optional[List[str]] = None) -> str:
        """Ask a question to the agent and get a response."""
        if not self.job_context:
            raise ValueError("Job context must be set before asking questions")

        # Create appropriate chain based on question type
        chain = (
            self._create_multiple_choice_chain(choices)
            if choices
            else self._create_open_ended_chain()
        )

        # Prepare input variables
        input_variables = {
            "history": self.messages,
            "question": question,
        }
        if choices:
            input_variables["choices"] = "\n".join(
                f"{i+1}. {choice}" for i, choice in enumerate(choices)
            )

        # Get response and update message history
        response = chain.invoke(input_variables)
        self.messages.append(HumanMessage(content=question))
        self.messages.append(AIMessage(content=response.content))

        return response.content


# Create global agent instance
survey_agent = SurveyAgent()


@app.route("/survey", methods=["POST"])
def handle_survey_question():
    """Handle incoming survey questions and return AI responses."""
    try:
        data = request.json
        required_fields = ["job_title", "job_description", "organization", "question"]
        if not all(field in data for field in required_fields):
            return (
                jsonify(
                    {"error": f"Missing required fields. Required: {required_fields}"}
                ),
                400,
            )

        # Set job context
        survey_agent.set_job_context(
            data["job_title"],
            data["job_description"],
            data["organization"],
        )

        # Get choices if provided
        choices = data.get("choices", [])

        # Get response
        response = survey_agent.ask_question(
            data["question"],
            choices if choices else None,
        )

        if choices:
            # Remove the number prefix from the response if present
            if response[0].isdigit():
                response = response.split(".", 1)[1].strip()

        return jsonify({"response": response})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Note: Debug mode should not be used in production
    app.run(port=5001)
