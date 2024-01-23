import openai
from openai.error import OpenAIError
import time
import streamlit as st


def main():
    st.set_page_config(
        page_title="OpenAI Assistant with Retrieval",
        page_icon="📚",
    )

    api_key = st.secrets["OPENAI_API_KEY"]
    assistant_id = st.secrets["ASSISTANT_ID"]
    openai.api_key = api_key

    # Initiate st.session_state
    if "client" not in st.session_state:
        st.session_state.client = openai

    if "messages" not in st.session_state:
        st.session_state.messages = []

    if "start_chat" not in st.session_state:
        st.session_state.start_chat = False

    if st.session_state.client:
        st.session_state.start_chat = True

    if st.session_state.start_chat:
        # Display existing messages in the chat
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # Accept user input
        if prompt := st.chat_input(f"Zeptej se mě na cokoliv ohledně tvorby loga..."):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            # Display user message in chat message container
            with st.chat_message("user"):
                st.markdown(prompt)

            # Create a thread
            st.session_state.thread = st.session_state.client.Thread.create()

            # Add a Message to the thread
            st.session_state.client.Message.create(
                thread_id=st.session_state.thread.id,
                role="user",
                content=prompt,
            )

            try:
                # Create a run and tell the assistant at which thread to look at
                run = st.session_state.client.Run.create(
                    thread_id=st.session_state.thread.id,
                    assistant_id=assistant_id,
                )
            except OpenAIError as e:
                st.error(f"An error occurred while creating a run: {e}")
                return  # Stop execution if the run can't be created

            run = wait_for_complete(run, st.session_state.thread)

            # Once the run has completed, list the messages in the thread
            replies = st.session_state.client.Message.list(
                thread_id=st.session_state.thread.id
            )

            # Process and display the response
            processed_response = process_replies(replies)
            st.session_state.messages.append(
                {"role": "assistant", "content": processed_response}
            )
            with st.chat_message("assistant"):
                st.markdown(processed_response, unsafe_allow_html=True)


def wait_for_complete(run, thread):
    # Continuously check the status of a run until it neither 'queued' nor 'in progress'
    while run.status == "queued" or run.status == "in_progress":
        run = st.session_state.client.Run.retrieve(
            thread_id=thread.id,
            run_id=run.id,
        )
        time.sleep(0.5)
    return run


def process_replies(replies):
    citations = []

    # Iterate over all replies
    for r in replies:
        if r.role == "assistant":
            message_content = r.content[0].text
            annotations = message_content.annotations

            # Iterate over the annotations and add footnotes
            for index, annotation in enumerate(annotations):
                # Replace the text with a footnote
                message_content.value = message_content.value.replace(
                    annotation.text, f" [{index}]"
                )

                # Handle file citations
                if file_citation := getattr(annotation, "file_citation", None):
                    if file_citation.file_id:
                        cited_file = st.session_state.client.File.retrieve(
                            file_citation.file_id
                        )
                        citations.append(
                            f"[{index}] {file_citation.quote} from {cited_file.filename}"
                        )
                    else:
                        # Log an error or display a warning message
                        st.error(f"No file ID found for citation index {index}")

                # Handle file paths
                elif file_path := getattr(annotation, "file_path", None):
                    if file_path.file_id:
                        cited_file = st.session_state.client.File.retrieve(
                            file_path.file_id
                        )
                        citations.append(
                            f"[{index}] Click <here> to download {cited_file.filename}"
                        )
                    else:
                        # Log an error or display a warning message
                        st.error(f"No file ID found for file path index {index}")

    # Combine message content and citations
    full_response = message_content.value + "\n" + "\n".join(citations)
    return full_response


if __name__ == "__main__":
    main()
