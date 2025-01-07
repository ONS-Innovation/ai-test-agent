from typing import List, Optional

from flask import Flask, jsonify, request
from google.oauth2 import service_account
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

app = Flask(__name__)


# Load service account credentials
def load_credentials():
    credentials = service_account.Credentials.from_service_account_file(
        "service-account.json",
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    return credentials


class SurveyAgent:
    def __init__(self):
        credentials = load_credentials()
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-pro", google_auth_credentials=credentials, temperature=0.7
        )

        self.memory = ConversationBufferMemory(
            input_key="input",
            memory_key="chat_history",
            return_messages=True,
            output_key="response",
        )

        self.job_context = None
        self.chain = None

    def set_job_context(self, job_title: str, job_description: str, organization: str):
        """Set the job context for the agent"""
        self.job_context = f"""
        Professional Role Information:
        Job Title: {job_title}
        Job Description: {job_description}
        Organization's Activity: {organization}
        """

    def _create_open_ended_chain(self):
        """Create chain for open-ended questions"""
        prompt = PromptTemplate(
            input_variables=["input", "chat_history", "context"],
            template="""
            {context}
            
            You are participating in a survey. Please answer the following question 
            based on your professional role and experience. Keep your answer brief and focused,
            ideally 1-2 sentences.
            
            Previous conversation:
            {chat_history}
            
            Question: {input}
            
            Answer:""",
        )
        return self._create_chain_with_prompt(prompt)

    def _create_multiple_choice_chain(self, choices: List[str]):
        """Create chain for multiple choice questions"""
        choices_text = "\n".join([f"- {choice}" for choice in choices])
        prompt = PromptTemplate(
            input_variables=["input", "chat_history", "context"],
            template="""
            {context}
            
            You are participating in a survey. Please select the most appropriate answer 
            from the following choices based on your professional role and experience.
            You MUST choose one of the provided options, even if none seem perfect.
            If unsure, choose 'none of the above' if available, or the closest match.

            Available choices:
            {choices_text}
            
            Previous conversation:
            {chat_history}
            
            Question: {input}
            
            Instructions:
            1. You MUST select one of the exact options listed above
            2. Return ONLY the exact text of your chosen option
            3. Do not add any explanation or additional text
            4. If unsure, choose 'none of the above' if available
            
            Selected answer:""".replace(
                "{choices_text}", choices_text
            ),
        )
        return self._create_chain_with_prompt(prompt)

    def _create_chain_with_prompt(self, prompt):
        """Create a chain with the given prompt"""
        return LLMChain(
            llm=self.llm,
            prompt=prompt,
            memory=self.memory,
            output_key="response",
            verbose=True,
        )

    def ask_question(self, question: str, choices: Optional[List[str]] = None) -> str:
        """Ask a question to the agent"""
        if not self.job_context:
            raise ValueError("Job context must be set before asking questions")

        # Create appropriate chain based on question type
        self.chain = (
            self._create_multiple_choice_chain(choices)
            if choices
            else self._create_open_ended_chain()
        )

        response = self.chain.invoke({"input": question, "context": self.job_context})

        return response["response"]


# Create global agent instance
survey_agent = SurveyAgent()


@app.route("/survey", methods=["POST"])
def handle_survey_question():
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
            data["job_title"], data["job_description"], data["organization"]
        )

        # Get choices if provided
        choices = data.get("choices", [])

        # Get response
        response = survey_agent.ask_question(
            data["question"], choices if choices else None
        )

        return jsonify({"response": response})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5001)
