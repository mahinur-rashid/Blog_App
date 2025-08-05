# Blog App

A modern, full-stack blog and chat web application built with Flask, MongoDB, and Socket.IO. This project features user authentication, real-time chat, friend requests, blog posting, comments, upvotes/downvotes and notifications.

## Features

- User registration and login
- Create, edit, and delete blog posts
- Comment on blogs
- Upvote and downvote blogs
- Real-time private and global chat with friends
- Friend request system with autocomplete
- Profile management (username, gender, avatar)
- Notification dropdown for new messages and friend requests
- Responsive, modern UI with Bootstrap 5

## Demo

The app is deployed and available at: [https://demoblog-vrdg.onrender.com/](https://demoblog-vrdg.onrender.com/)

## Getting Started

### Prerequisites
- Python 3.8+
- MongoDB (local or Atlas)

### Installation

1. **Clone the repository:**
   ```sh
   git clone https://github.com/yourusername/Blog_App.git
   cd Blog_App
   ```
2. **Create a virtual environment and activate it:**
   ```sh
   python -m venv venv
   venv\Scripts\activate  # On Windows
   # or
   source venv/bin/activate  # On Mac/Linux
   ```
3. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```
4. **Set environment variables:**
   Create a `.env` file or set these in your environment:
   - `SECRET_KEY=your_secret_key_here`
   - `MONGO_URI=your_mongodb_uri_here`

5. **Run the app locally:**
   ```sh
   python app.py
   ```
   Or for Socket.IO support:
   ```sh
   python -m flask run
   # or
   flask run
   ```

6. **Access the app:**
   Open [http://localhost:5000](http://localhost:5000) in your browser.

## Deployment

This app is deployed on [Render](https://render.com/). You can deploy it to any cloud provider that supports Python and MongoDB.

## Folder Structure

- `app.py` - Main Flask application
- `static/` - Static files (CSS, JS, images)
- `templates/` - Jinja2 HTML templates
- `requirements.txt` - Python dependencies
- `Procfile` - For deployment (e.g., Gunicorn)

## Security
- **Never commit your real MongoDB credentials or secret keys.**
- Use environment variables for all sensitive information.
- The `.gitignore` is set up to exclude local databases, credentials, and virtual environments.

## License

This project is open source and available under the [MIT License](LICENSE).

---

**Deployed at:** [https://demoblog-vrdg.onrender.com/](https://demoblog-vrdg.onrender.com/)

---

*Feel free to contribute or open issues!*
