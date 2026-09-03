import streamlit as st
import requests
import base64
import urllib.parse

st.set_page_config(page_title="Simple Social", layout="wide")

# Initialize session state
if 'token' not in st.session_state:
    st.session_state.token = None
if 'user' not in st.session_state:
    st.session_state.user = None


API_BASE = "http://localhost:8000"

def get_headers():
    """Get authorization headers with token"""
    if st.session_state.token:
        return {"Authorization": f"Bearer {st.session_state.token}"}
    return {}


def login_page():
    st.title("🚀 Welcome to Simple Social")

    # Simple form with two buttons
    email = st.text_input("Email:")
    password = st.text_input("Password:", type="password")

    if email and password:
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Login", type="primary", use_container_width=True):
                # Login using FastAPI Users JWT endpoint
                login_data = {"username": email, "password": password}
                try:
                    response = requests.post(f"{API_BASE}/auth/jwt/login", data=login_data)
                    if response.status_code == 200:
                        token_data = response.json()
                        st.session_state.token = token_data["access_token"]

                        # Get user info
                        user_response = requests.get(f"{API_BASE}/users/me", headers=get_headers())
                        if user_response.status_code == 200:
                            st.session_state.user = user_response.json()
                            st.rerun()
                        else:
                            st.error("Failed to get user info")
                    else:
                        st.error("Invalid email or password!")
                except requests.exceptions.ConnectionError:
                    st.error("🔌 Could not connect to backend server. Make sure the FastAPI server is running: `uv run uvicorn app.app:app --reload --port 8000`")

        with col2:
            if st.button("Sign Up", type="secondary", use_container_width=True):
                # Register using FastAPI Users
                signup_data = {"email": email, "password": password}
                try:
                    response = requests.post(f"{API_BASE}/auth/register", json=signup_data)
                    if response.status_code == 201:
                        st.success("Account created! Click Login now.")
                    else:
                        err = response.json().get("detail", "Registration failed")
                        if isinstance(err, list):
                            error_detail = ", ".join(item.get("msg", str(item)) for item in err)
                        elif err == "REGISTER_USER_ALREADY_EXISTS":
                            error_detail = "An account with this email already exists. Please log in."
                        else:
                            error_detail = str(err)
                        st.error(f"Registration failed: {error_detail}")
                except requests.exceptions.ConnectionError:
                    st.error("🔌 Could not connect to backend server. Make sure the FastAPI server is running: `uv run uvicorn app.app:app --reload --port 8000`")
    else:
        st.info("Enter your email and password above")


def upload_page():
    st.title("📸 Share Something")

    uploaded_file = st.file_uploader("Choose media", type=['png', 'jpg', 'jpeg', 'mp4', 'avi', 'mov', 'mkv', 'webm'])
    caption = st.text_area("Caption:", placeholder="What's on your mind?")

    if uploaded_file and st.button("Share", type="primary"):
        with st.spinner("Uploading..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
            data = {"caption": caption}
            try:
                response = requests.post(f"{API_BASE}/upload", files=files, data=data, headers=get_headers())
                if response.status_code == 200:
                    st.success("Posted!")
                    st.rerun()
                else:
                    detail = response.json().get("detail", "Upload failed") if response.headers.get("content-type") == "application/json" else response.text
                    st.error(f"Upload failed: {detail}")
            except requests.exceptions.ConnectionError:
                st.error("🔌 Could not connect to backend server. Make sure FastAPI is running on port 8000.")


def encode_text_for_overlay(text):
    """Encode text for ImageKit overlay - base64 then URL encode"""
    if not text:
        return ""
    # Base64 encode the text
    base64_text = base64.b64encode(text.encode('utf-8')).decode('utf-8')
    # URL encode the result
    return urllib.parse.quote(base64_text)


def create_transformed_url(original_url, transformation_params, caption=None):
    if not original_url or not isinstance(original_url, str) or not original_url.startswith("http"):
        return original_url or ""

    if caption:
        encoded_caption = encode_text_for_overlay(caption)
        # Add text overlay at bottom with semi-transparent background
        text_overlay = f"l-text,ie-{encoded_caption},ly-N20,lx-20,fs-100,co-white,bg-000000A0,l-end"
        transformation_params = text_overlay

    if not transformation_params:
        return original_url

    parts = original_url.split("/")
    # ImageKit URLs typically have: https://ik.imagekit.io/<id>/<path> (at least 5 segments)
    if len(parts) < 5 or "imagekit.io" not in original_url:
        return original_url

    file_path = "/".join(parts[4:])
    base_url = "/".join(parts[:4])
    return f"{base_url}/tr:{transformation_params}/{file_path}"


def feed_page():
    st.title("🏠 Feed")

    try:
        response = requests.get(f"{API_BASE}/feed", headers=get_headers())
    except requests.exceptions.ConnectionError:
        st.error("🔌 Could not connect to backend server at http://localhost:8000. Please start the FastAPI backend: `uv run uvicorn app.app:app --reload --port 8000`")
        return

    if response.status_code == 200:
        posts = response.json().get("posts", [])

        if not posts:
            st.info("No posts yet! Be the first to share something.")
            return

        for post in posts:
            st.markdown("---")

            # Header with user, date, and delete button (if owner)
            col1, col2 = st.columns([4, 1])
            with col1:
                created_date = post.get('created_at', '')[:10] if post.get('created_at') else ''
                st.markdown(f"**{post.get('email', 'Anonymous')}** • {created_date}")
            with col2:
                if post.get('is_owner', False):
                    if st.button("🗑️", key=f"delete_{post['id']}", help="Delete post"):
                        # Delete the post
                        try:
                            del_response = requests.delete(f"{API_BASE}/posts/{post['id']}", headers=get_headers())
                            if del_response.status_code == 200:
                                st.success("Post deleted!")
                                st.rerun()
                            else:
                                del_detail = del_response.json().get("detail", "Failed to delete post")
                                st.error(f"Failed to delete post: {del_detail}")
                        except requests.exceptions.ConnectionError:
                            st.error("🔌 Could not connect to backend server to delete post.")

            # Uniform media display with caption overlay
            caption = post.get('caption', '')
            post_url = post.get('url', '')
            file_type = post.get('file_type', 'image')

            try:
                if file_type in ['image', 'photo']:
                    uniform_url = create_transformed_url(post_url, "", caption)
                    st.image(uniform_url, width=300)
                else:
                    # For videos: specify only height to maintain aspect ratio + caption overlay
                    uniform_video_url = create_transformed_url(post_url, "w-400,h-200,cm-pad_resize,bg-blurred")
                    st.video(uniform_video_url, width=300)
                    st.caption(caption)
            except Exception as e:
                st.warning(f"Could not display media: {e}")

            st.markdown("")  # Space between posts
    else:
        error_msg = response.json().get("detail", response.text) if "application/json" in response.headers.get("content-type", "") else response.text
        st.error(f"Failed to load feed ({response.status_code}): {error_msg}")


# Main app logic
if st.session_state.user is None:
    login_page()
else:
    # Sidebar navigation
    st.sidebar.title(f"👋 Hi {st.session_state.user['email']}!")

    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.session_state.token = None
        st.rerun()

    st.sidebar.markdown("---")
    page = st.sidebar.radio("Navigate:", ["🏠 Feed", "📸 Upload"])

    if page == "🏠 Feed":
        feed_page()
    else:
        upload_page()