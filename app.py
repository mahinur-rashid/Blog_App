import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from flask_pymongo import PyMongo
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId

# Flask app setup
app = Flask(__name__)
import os
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key_here')
app.config['MONGO_URI'] = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/blog')

# Extensions
mongo = PyMongo(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
socketio = SocketIO(app, cors_allowed_origins="*")

# Default avatar paths
DEFAULT_AVATAR_MALE = '/static/default_avatar_male.jpg'
DEFAULT_AVATAR_FEMALE = '/static/default_avatar_female.jpg'
DEFAULT_GLOBAL_AVATAR = '/static/Default_global_img.jpg'






def chat_history(user_id):
    from bson import ObjectId
    my_id = ObjectId(current_user.id)
    if user_id == 'global':
        messages = list(mongo.db.messages.find({'is_global': True}).sort('timestamp', 1))
        unread_count = 0
        # Attach avatar_url for each sender
        for msg in messages:
            sender_doc = mongo.db.users.find_one({'_id': msg['sender_id']}) if 'sender_id' in msg else None
            if sender_doc and sender_doc.get('avatar'):
                msg['avatar_url'] = sender_doc['avatar']
            else:
                gender = sender_doc.get('gender') if sender_doc else 'male'
                msg['avatar_url'] = '/static/default_avatar_female.jpg' if gender == 'female' else '/static/default_avatar_male.jpg'
    else:
        try:
            other_id = ObjectId(user_id)
        except Exception:
            return {'messages': [], 'unread_count': 0}
        # Only allow chat history for users in sidebar (friends, others, message requests)
        allowed_ids = [str(u['_id']) for u in mongo.db.users.find({'_id': {'$ne': my_id}})]
        if user_id not in allowed_ids:
            return {'messages': [], 'unread_count': 0}
        messages = list(mongo.db.messages.find({
            '$or': [
                {'sender_id': my_id, 'receiver_id': other_id},
                {'sender_id': other_id, 'receiver_id': my_id}
            ]
        }).sort('timestamp', 1))
        unread_count = mongo.db.messages.count_documents({
            'sender_id': other_id,
            'receiver_id': my_id,
            'seen': False,
            f'deleted_{my_id}': {'$ne': True}
        })
    def get_username(uid):
        user = mongo.db.users.find_one({'_id': ObjectId(uid)}) if uid != 'global' else None
        return user['username'] if user else 'Unknown'
    result = []
    for msg in messages:
        result.append({
            '_id': str(msg['_id']),
            'sender_id': str(msg['sender_id']),
            'sender_username': get_username(msg['sender_id']),
            'content': msg.get('content'),
            'timestamp': msg.get('timestamp').isoformat() if msg.get('timestamp') else '',
            'seen': msg.get('seen', False),
            'avatar_url': msg.get('avatar_url', '/static/Default_global_img.jpg')
        })
    return {'messages': result, 'unread_count': unread_count}


@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_doc = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    # Get pending friend requests sent to current user
    friend_requests = list(mongo.db.friend_requests.find({'to_id': ObjectId(current_user.id), 'status': 'pending'}))
    if request.method == 'POST':
        username = request.form.get('username')
        gender = request.form.get('gender')
        update_fields = {}
        if username and username != user_doc['username']:
            existing_user = mongo.db.users.find_one({'username': username})
            if existing_user and str(existing_user['_id']) != str(current_user.id):
                flash('Username already exists. Please choose another.')
            else:
                update_fields['username'] = username
        if gender:
            update_fields['gender'] = gender
        if update_fields:
            mongo.db.users.update_one({'_id': ObjectId(current_user.id)}, {'$set': update_fields})
            flash('Profile updated.')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=user_doc, friend_requests=friend_requests)

@app.route('/profile/password', methods=['POST'])
@login_required
def update_password():
    old_pw = request.form.get('old_password')
    new_pw = request.form.get('new_password')
    user_doc = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    if not check_password_hash(user_doc['password_hash'], old_pw):
        flash('Old password incorrect.')
        return redirect(url_for('profile'))
    mongo.db.users.update_one({'_id': ObjectId(current_user.id)}, {'$set': {'password_hash': generate_password_hash(new_pw)}})
    flash('Password updated.')
    return redirect(url_for('profile'))

# Friends section
@app.route('/friends')
@login_required
def friends():
    user_id = ObjectId(current_user.id)
    # Get accepted friends
    requests = list(mongo.db.friend_requests.find({
        '$or': [
            {'from_id': user_id, 'status': 'accepted'},
            {'to_id': user_id, 'status': 'accepted'}
        ]
    }))
    friend_ids = set()
    for req in requests:
        if req['from_id'] == user_id:
            friend_ids.add(req['to_id'])
        else:
            friend_ids.add(req['from_id'])
    friends = list(mongo.db.users.find({'_id': {'$in': list(friend_ids)}}))
    # Get pending friend requests sent to current user
    raw_friend_requests = list(mongo.db.friend_requests.find({'to_id': user_id, 'status': 'pending'}))
    friend_requests = []
    for req in raw_friend_requests:
        from_user = mongo.db.users.find_one({'_id': req['from_id']})
        friend_requests.append({
            'from_username': req['from_username'],
            'from_id': str(req['from_id']),
            'avatar': from_user['avatar'] if from_user and from_user.get('avatar') else ('/static/default_avatar_female.png' if from_user and from_user.get('gender') == 'female' else '/static/default_avatar_male.png'),
            'gender': from_user['gender'] if from_user and from_user.get('gender') else 'male',
            '_id': str(req['_id'])
        })
    # Get sent friend requests (pending)
    sent_requests = list(mongo.db.friend_requests.find({'from_id': user_id, 'status': 'pending'}))
    # For each sent request, get the user info for to_id
    sent_request_users = []
    for req in sent_requests:
        to_user = mongo.db.users.find_one({'_id': req['to_id']})
        sent_request_users.append({
            'username': to_user['username'] if to_user else 'Unknown',
            'avatar': to_user['avatar'] if to_user and to_user.get('avatar') else ('/static/default_avatar_female.png' if to_user and to_user.get('gender') == 'female' else '/static/default_avatar_male.png'),
            'gender': to_user['gender'] if to_user and to_user.get('gender') else 'male',
            'status': req['status'],
            'to_id': str(req['to_id'])
        })
    return render_template('friends.html', friends=friends, friend_requests=friend_requests, sent_requests=sent_request_users)

@app.route('/friend_request/send', methods=['POST'])
@login_required
def send_friend_request_by_username():
    username = request.form.get('username')
    to_user = mongo.db.users.find_one({'username': username})
    if not to_user:
        flash('User not found.')
        return redirect(url_for('friends'))
    if to_user['_id'] == ObjectId(current_user.id):
        flash('Cannot send request to yourself.')
        return redirect(url_for('friends'))
    existing = mongo.db.friend_requests.find_one({
        'from_id': ObjectId(current_user.id),
        'to_id': to_user['_id']
    })
    if existing:
        flash('Friend request already sent.')
        return redirect(url_for('friends'))
    request_doc = {
        'from_id': ObjectId(current_user.id),
        'from_username': current_user.username,
        'to_id': to_user['_id'],
        'timestamp': datetime.datetime.utcnow(),
        'status': 'pending'
    }
    mongo.db.friend_requests.insert_one(request_doc)
    flash('Friend request sent.')
    return redirect(url_for('friends'))

@app.route('/user/<user_id>')
@login_required
def view_user_profile(user_id):
    user = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if not user:
        return 'User not found', 404
    # Get blogs written by this user
    blogs = list(mongo.db.blogs.find({'author_id': ObjectId(user_id)}).sort('timestamp', -1))
    for blog in blogs:
        # Get comment count for each blog
        blog['comment_count'] = mongo.db.comments.count_documents({'blog_id': blog['_id']})
        # Get upvote/downvote counts
        upvotes = blog.get('upvotes', [])
        downvotes = blog.get('downvotes', [])
        if isinstance(upvotes, int):
            upvotes = []
        if isinstance(downvotes, int):
            downvotes = []
        blog['upvotes'] = upvotes
        blog['downvotes'] = downvotes
        blog['upvote_count'] = len(upvotes)
        blog['downvote_count'] = len(downvotes)
        # Get user info for upvoters
        blog['upvoters'] = []
        for uid in upvotes:
            voter = mongo.db.users.find_one({'_id': uid})
            if voter:
                blog['upvoters'].append({
                    'username': voter['username'],
                    'avatar': voter['avatar'] if voter.get('avatar') else ('/static/default_avatar_female.png' if voter.get('gender') == 'female' else '/static/default_avatar_male.png')
                })
        # Get user info for downvoters
        blog['downvoters'] = []
        for uid in downvotes:
            voter = mongo.db.users.find_one({'_id': uid})
            if voter:
                blog['downvoters'].append({
                    'username': voter['username'],
                    'avatar': voter['avatar'] if voter.get('avatar') else ('/static/default_avatar_female.png' if voter.get('gender') == 'female' else '/static/default_avatar_male.png')
                })
    return render_template('user_profile.html', user=user, blogs=blogs)


@app.route('/chat/global_history')
@login_required
def global_history():
    messages = list(mongo.db.messages.find({'is_global': True}).sort('timestamp', 1))
    def get_username(uid):
        user = mongo.db.users.find_one({'_id': uid})
        return user['username'] if user else 'Unknown'
    result = []
    for msg in messages:
        result.append({
            '_id': str(msg['_id']) if '_id' in msg else '',
            'sender_id': str(msg['sender_id']) if 'sender_id' in msg else '',
            'sender_username': get_username(msg['sender_id']) if 'sender_id' in msg else '',
            'content': msg.get('content'),
            'timestamp': msg.get('timestamp').isoformat() if msg.get('timestamp') else '',
            'seen': msg.get('seen', False)
        })
    return {'messages': result}
class User(UserMixin):
    def __init__(self, user_doc):
        self.id = str(user_doc['_id'])
        self.username = user_doc['username']
        self.email = user_doc['email']
        self.password_hash = user_doc['password_hash']
        self.gender = user_doc.get('gender', 'male')
        self.avatar = user_doc.get('avatar')

@login_manager.user_loader
def load_user(user_id):
    from bson import ObjectId
    user_doc = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if user_doc:
        return User(user_doc)
    return None

@app.route('/')
def index():
    blogs = list(mongo.db.blogs.find().sort('timestamp', -1))
    for blog in blogs:
        author = mongo.db.users.find_one({'_id': blog['author_id']})
        blog['author'] = author
        # Get comment count for each blog
        blog['comment_count'] = mongo.db.comments.count_documents({'blog_id': blog['_id']})
        # Get upvote/downvote counts
        # Ensure upvotes/downvotes are lists, not ints
        upvotes = blog.get('upvotes', [])
        downvotes = blog.get('downvotes', [])
        if isinstance(upvotes, int):
            upvotes = []
        if isinstance(downvotes, int):
            downvotes = []
        blog['upvotes'] = upvotes
        blog['downvotes'] = downvotes
        blog['upvote_count'] = len(upvotes)
        blog['downvote_count'] = len(downvotes)
        # Get user info for upvoters
        blog['upvoters'] = []
        for uid in upvotes:
            user = mongo.db.users.find_one({'_id': uid})
            if user:
                blog['upvoters'].append({
                    'username': user['username'],
                    'avatar': user['avatar'] if user.get('avatar') else ('/static/default_avatar_female.png' if user.get('gender') == 'female' else '/static/default_avatar_male.png')
                })
        # Get user info for downvoters
        blog['downvoters'] = []
        for uid in downvotes:
            user = mongo.db.users.find_one({'_id': uid})
            if user:
                blog['downvoters'].append({
                    'username': user['username'],
                    'avatar': user['avatar'] if user.get('avatar') else ('/static/default_avatar_female.png' if user.get('gender') == 'female' else '/static/default_avatar_male.png')
                })
    return render_template('index.html', blogs=blogs)
@app.route('/blog/<blog_id>/upvote', methods=['POST'])
@login_required
def upvote_blog(blog_id):
    from bson import ObjectId
    blog = mongo.db.blogs.find_one({'_id': ObjectId(blog_id)})
    user_id = ObjectId(current_user.id)
    if blog:
        # Remove from downvotes if present
        mongo.db.blogs.update_one({'_id': ObjectId(blog_id)}, {'$pull': {'downvotes': user_id}})
        # Ensure upvotes is a list
        upvotes = blog.get('upvotes', [])
        if isinstance(upvotes, int):
            upvotes = []
        # Add to upvotes if not present
        if user_id not in upvotes:
            mongo.db.blogs.update_one({'_id': ObjectId(blog_id)}, {'$push': {'upvotes': user_id}})
    return redirect(url_for('index'))

@app.route('/blog/<blog_id>/downvote', methods=['POST'])
@login_required
def downvote_blog(blog_id):
    from bson import ObjectId
    blog = mongo.db.blogs.find_one({'_id': ObjectId(blog_id)})
    user_id = ObjectId(current_user.id)
    if blog:
        # Remove from upvotes if present
        mongo.db.blogs.update_one({'_id': ObjectId(blog_id)}, {'$pull': {'upvotes': user_id}})
        # Ensure downvotes is a list
        downvotes = blog.get('downvotes', [])
        if isinstance(downvotes, int):
            downvotes = []
        # Add to downvotes if not present
        if user_id not in downvotes:
            mongo.db.blogs.update_one({'_id': ObjectId(blog_id)}, {'$push': {'downvotes': user_id}})
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        # Enforce unique username
        if mongo.db.users.find_one({'username': username}):
            flash('Username already exists. Please choose another.')
            return redirect(url_for('register'))
        hashed_pw = generate_password_hash(password)
        user_doc = {
            'username': username,
            'email': email,
            'password_hash': hashed_pw
        }
        mongo.db.users.insert_one(user_doc)
        flash('Account created! Please log in.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_doc = mongo.db.users.find_one({'username': username})
        if user_doc and check_password_hash(user_doc['password_hash'], password):
            user = User(user_doc)
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/blog/new', methods=['GET', 'POST'])
@login_required
def new_blog():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        from bson import ObjectId
        blog_doc = {
            'title': title,
            'content': content,
            'author_id': ObjectId(current_user.id),
            'timestamp': datetime.datetime.utcnow()
        }
        mongo.db.blogs.insert_one(blog_doc)
        return redirect(url_for('index'))
    return render_template('blog.html')

@app.route('/blog/<blog_id>/delete', methods=['POST'])
@login_required
def delete_blog(blog_id):
    from bson import ObjectId
    blog = mongo.db.blogs.find_one({'_id': ObjectId(blog_id)})
    if not blog:
        flash('Blog not found.')
        return redirect(url_for('index'))
    if blog['author_id'] != ObjectId(current_user.id):
        flash('You are not authorized to delete this blog.')
        return redirect(url_for('view_blog', blog_id=blog_id))
    mongo.db.blogs.delete_one({'_id': ObjectId(blog_id)})
    mongo.db.comments.delete_many({'blog_id': ObjectId(blog_id)})
    flash('Blog deleted.')
    return redirect(url_for('index'))
@app.route('/blog/<blog_id>')
def view_blog(blog_id):
    from bson import ObjectId
    try:
        blog = mongo.db.blogs.find_one({'_id': ObjectId(blog_id)})
    except Exception:
        return "Blog not found", 404
    if not blog:
        return "Blog not found", 404
    author = mongo.db.users.find_one({'_id': blog['author_id']})
    raw_comments = list(mongo.db.comments.find({'blog_id': ObjectId(blog_id)}).sort('timestamp', 1))
    comments = []
    for comment in raw_comments:
        user = mongo.db.users.find_one({'_id': comment['author_id']})
        if user and user.get('avatar'):
            avatar_url = user['avatar']
        else:
            avatar_url = '/static/default_avatar_female.png' if user and user.get('gender') == 'female' else '/static/default_avatar_male.png'
        comment['avatar_url'] = avatar_url
        comments.append(comment)
    return render_template('view_blog.html', blog=blog, author=author, comments=comments)

@app.route('/blog/<blog_id>/comment', methods=['POST'])
@login_required
def add_comment(blog_id):
    from bson import ObjectId
    content = request.form.get('comment')
    if not content:
        flash('Comment cannot be empty.')
        return redirect(url_for('view_blog', blog_id=blog_id))
    comment_doc = {
        'blog_id': ObjectId(blog_id),
        'author_id': ObjectId(current_user.id),
        'author_username': current_user.username,
        'content': content,
        'timestamp': datetime.datetime.utcnow()
    }
    mongo.db.comments.insert_one(comment_doc)
    return redirect(url_for('view_blog', blog_id=blog_id))

@app.route('/notifications')
@login_required
def notifications():
    from bson import ObjectId
    user_id = ObjectId(current_user.id)
    # Example: show pending friend requests and unread messages
    requests = list(mongo.db.friend_requests.find({'to_id': user_id, 'status': 'pending'}))
    messages = list(mongo.db.messages.find({'receiver_id': user_id, 'is_global': {'$ne': True}}).sort('timestamp', -1))
    notifs = []
    for req in requests:
        notifs.append({'type': 'friend_request', 'text': f"Friend request from {req['from_username']}", 'timestamp': req['timestamp']})
    for msg in messages:
        sender_doc = mongo.db.users.find_one({'_id': msg['sender_id']})
        sender_name = sender_doc['username'] if sender_doc else 'Unknown'
        notifs.append({'type': 'message', 'text': f"Message from {sender_name}: {msg['content']}", 'timestamp': msg['timestamp']})
    notifs.sort(key=lambda x: x['timestamp'], reverse=True)
    # Return as JSON for dropdown
    return {'notifications': [
        {
            'type': n['type'],
            'text': n['text'],
            'timestamp': n['timestamp'].isoformat() if n['timestamp'] else ''
        } for n in notifs
    ]}

# Mark notification/message as read
@app.route('/notifications/read/<notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    from bson import ObjectId
    # Try to mark friend request as read
    result = mongo.db.friend_requests.update_one({'_id': ObjectId(notif_id), 'to_id': ObjectId(current_user.id)}, {'$set': {'read': True}})
    # If not found, try to mark message as read
    if result.matched_count == 0:
        mongo.db.messages.update_one({'_id': ObjectId(notif_id), 'receiver_id': ObjectId(current_user.id)}, {'$set': {'read': True}})
    return {'status': 'success'}
@app.route('/chat')
@login_required
@login_required
def chat():
    from bson import ObjectId
    user_id = ObjectId(current_user.id)
    # Get friend ids
    requests = list(mongo.db.friend_requests.find({
        '$or': [
            {'from_id': user_id, 'status': 'accepted'},
            {'to_id': user_id, 'status': 'accepted'}
        ]
    }))
    friend_ids = set()
    for req in requests:
        if req['from_id'] == user_id:
            friend_ids.add(req['to_id'])
        else:
            friend_ids.add(req['from_id'])
    friends = list(mongo.db.users.find({'_id': {'$in': list(friend_ids)}}))
    # Add unread message count for each friend
    for friend in friends:
        unread_count = mongo.db.messages.count_documents({
            'sender_id': friend['_id'],
            'receiver_id': user_id,
            'seen': False,
            f'deleted_{user_id}': {'$ne': True}
        })
        friend['unread_count'] = unread_count
    # Get all users except current user
    all_users = list(mongo.db.users.find({'_id': {'$ne': user_id}}))
    users = []
    message_requests = []
    for user in all_users:
        user['is_friend'] = user['_id'] in friend_ids
        # Check if user has messaged me and is not a friend
        has_messaged_me = mongo.db.messages.count_documents({
            'sender_id': user['_id'],
            'receiver_id': user_id
        }) > 0
        user['has_messaged_me'] = has_messaged_me
        # Set avatar_url for template
        if 'avatar' in user and user['avatar']:
            user['avatar_url'] = user['avatar']
        else:
            user['avatar_url'] = '/static/default_avatar_female.jpg' if user.get('gender') == 'female' else '/static/default_avatar_male.jpg'
        # Optionally set last_message
        last_msg = mongo.db.messages.find_one({
            '$or': [
                {'sender_id': user['_id'], 'receiver_id': user_id},
                {'sender_id': user_id, 'receiver_id': user['_id']}
            ]
        }, sort=[('timestamp', -1)])
        user['last_message'] = last_msg['content'] if last_msg else ''
        if not user['is_friend'] and has_messaged_me:
            message_requests.append(user)
        else:
            users.append(user)
    current_user_doc = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})
    if current_user_doc:
        if 'avatar' in current_user_doc and current_user_doc['avatar']:
            current_avatar = current_user_doc['avatar']
        else:
            current_avatar = '/static/default_avatar_female.jpg' if current_user_doc.get('gender') == 'female' else '/static/default_avatar_male.jpg'
    else:
        current_avatar = '/static/default_avatar_male.jpg'
    return render_template('chat.html', users=users, message_requests=message_requests, current_avatar=current_avatar)
    from bson import ObjectId
    my_id = ObjectId(current_user.id)
    if user_id == 'global':
        # Global chat: fetch all messages with receiver_id == 'global'
        messages = list(mongo.db.messages.find({
            'receiver_id': 'global'
        }).sort('timestamp', 1))
        def get_username(uid):
            user = mongo.db.users.find_one({'_id': uid})
            return user['username'] if user else 'Unknown'
        result = []
        for msg in messages:
            result.append({
                '_id': str(msg['_id']),
                'sender_id': str(msg['sender_id']),
                'sender_username': get_username(msg['sender_id']),
                'content': msg.get('content'),
                'timestamp': msg.get('timestamp').isoformat() if msg.get('timestamp') else '',
                'seen': msg.get('seen', False),
                'avatar_url': DEFAULT_GLOBAL_AVATAR
            })
        return {'messages': result}
    else:
        try:
            other_id = ObjectId(user_id)
        except Exception:
            return {'messages': []}
        messages = list(mongo.db.messages.find({
            '$or': [
                {'sender_id': my_id, 'receiver_id': other_id},
                {'sender_id': other_id, 'receiver_id': my_id}
            ]
        }).sort('timestamp', 1))
        # Count unread messages for current user (receiver)
        unread_count = mongo.db.messages.count_documents({
            'sender_id': other_id,
            'receiver_id': my_id,
            'seen': False,
            f'deleted_{my_id}': {'$ne': True}
        })
        def get_username(uid):
            user = mongo.db.users.find_one({'_id': uid})
            return user['username'] if user else 'Unknown'
        result = []
        for msg in messages:
            result.append({
                '_id': str(msg['_id']),
                'sender_id': str(msg['sender_id']),
                'sender_username': get_username(msg['sender_id']),
                'content': msg.get('content'),
                'timestamp': msg.get('timestamp').isoformat() if msg.get('timestamp') else '',
                'seen': msg.get('seen', False)
            })
        return {'messages': result, 'unread_count': unread_count}

@app.route('/chat/history/<user_id>')
@login_required
def chat_history_api(user_id):
    return jsonify(chat_history(user_id))

from flask import jsonify
# Delete a single message (only if current user is sender)
@app.route('/chat/message/<msg_id>/delete', methods=['POST'])
@login_required
def delete_message(msg_id):
    msg = mongo.db.messages.find_one({'_id': ObjectId(msg_id)})
    if not msg or str(msg.get('sender_id')) != current_user.id:
        return jsonify({'status': 'error', 'message': 'Not allowed or message not found.'}), 403
    # Instead of deleting, mark as deleted for current user
    mongo.db.messages.update_one({'_id': ObjectId(msg_id)}, {'$set': {f'deleted_{current_user.id}': True}})
    # Only emit delete event to current user (not other end)
    socketio.emit('delete_message', {'msg_id': msg_id}, room=str(current_user.id))
    return jsonify({'status': 'success'})

# Delete all messages in a conversation (from current user's end only)
@app.route('/chat/conversation/<user_id>/delete', methods=['POST'])
@login_required
def delete_conversation(user_id):
    my_id = ObjectId(current_user.id)
    other_id = ObjectId(user_id)
    # Find all messages between users
    msgs = list(mongo.db.messages.find({
        '$or': [
            {'sender_id': my_id, 'receiver_id': other_id},
            {'sender_id': other_id, 'receiver_id': my_id}
        ],
        '$or': [
            {'sender_id': my_id},
            {'receiver_id': my_id}
        ]
    }))
    # Mark as deleted for current user only
    for msg in msgs:
        mongo.db.messages.update_one({'_id': msg['_id']}, {'$set': {f'deleted_{current_user.id}': True}})
        socketio.emit('delete_message', {'msg_id': str(msg['_id'])}, room=str(current_user.id))
    return jsonify({'status': 'success', 'deleted_count': len(msgs)})

@app.route('/friend_request/<user_id>', methods=['POST'])
@login_required
def send_friend_request(user_id):
    from bson import ObjectId
    if ObjectId(user_id) == ObjectId(current_user.id):
        flash('You cannot send a friend request to yourself.')
        return redirect(url_for('chat'))
    existing = mongo.db.friend_requests.find_one({
        'from_id': ObjectId(current_user.id),
        'to_id': ObjectId(user_id)
    })
    if existing:
        flash('Friend request already sent.')
        return redirect(url_for('chat'))
    request_doc = {
        'from_id': ObjectId(current_user.id),
        'from_username': current_user.username,
        'to_id': ObjectId(user_id),
        'timestamp': datetime.datetime.utcnow(),
        'status': 'pending'
    }
    mongo.db.friend_requests.insert_one(request_doc)
    flash('Friend request sent.')
    return redirect(url_for('chat'))
# Accept friend request
@app.route('/friend_request/accept/<req_id>', methods=['POST'])
@login_required
def accept_friend_request(req_id):
    from bson import ObjectId
    req = mongo.db.friend_requests.find_one({'_id': ObjectId(req_id), 'to_id': ObjectId(current_user.id), 'status': 'pending'})
    if not req:
        flash('Friend request not found.')
        return redirect(url_for('friends'))
    mongo.db.friend_requests.update_one({'_id': ObjectId(req_id)}, {'$set': {'status': 'accepted'}})
    flash('Friend request accepted.')
    return redirect(url_for('friends'))

# Decline friend request
@app.route('/friend_request/decline/<req_id>', methods=['POST'])
@login_required
def decline_friend_request(req_id):
    from bson import ObjectId
    req = mongo.db.friend_requests.find_one({'_id': ObjectId(req_id), 'to_id': ObjectId(current_user.id), 'status': 'pending'})
    if not req:
        flash('Friend request not found.')
        return redirect(url_for('friends'))
    mongo.db.friend_requests.delete_one({'_id': ObjectId(req_id)})
    flash('Friend request declined.')
    return redirect(url_for('friends'))
@socketio.on('send_message')
def handle_send_message(data):
    from bson import ObjectId
    sender = current_user.username
    sender_id = str(current_user.id)
    receiver = data['receiver']
    receiver_id = data['receiver_id']
    content = data['content']
    is_global = data.get('is_global', False)
    msg_doc = {
        'sender_id': ObjectId(current_user.id),
        'sender_username': sender,
        'content': content,
        'timestamp': datetime.datetime.utcnow(),
        'is_global': is_global,
        'seen': False
    }
    if is_global:
        msg_doc['receiver_id'] = 'global'
    else:
        msg_doc['receiver_id'] = ObjectId(receiver_id)
    result = mongo.db.messages.insert_one(msg_doc)
    msg_id = str(result.inserted_id)
    emit_data = {
        '_id': msg_id,
        'sender': sender,
        'sender_id': sender_id,
        'sender_username': sender,
        'receiver_id': receiver_id,
        'content': content,
        'is_global': is_global,
        'seen': False,
        'notification': f'Message from {sender}'
    }
    # Real-time event emission for Messenger-like experience
    if is_global:
        socketio.emit('new_message', emit_data, broadcast=True)
    else:
        # Emit to both sender and receiver rooms for instant update
        socketio.emit('new_message', emit_data, room=sender_id)
        socketio.emit('new_message', emit_data, room=receiver_id)

# Autocomplete usernames for friend requests
@app.route('/api/user_search')
@login_required
def user_search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    all_users = list(mongo.db.users.find({}))
    query_lower = query.lower()
    unique_results = set()
    final_results = []
    for user in all_users:
        uname = user.get('username', '')
        uname_lower = uname.lower()
        user_id_str = str(user['_id'])
        # Exclude current user from results
        if uname_lower == current_user.username.lower():
            continue
        if query_lower in uname_lower:
            key = (uname_lower, user_id_str)
            if key not in unique_results:
                avatar = user.get('avatar')
                if not avatar or len(avatar) < 10:
                    avatar = DEFAULT_AVATAR_FEMALE if user.get('gender') == 'female' else DEFAULT_AVATAR_MALE
                final_results.append({
                    'username': uname,
                    'avatar': avatar,
                    'id': user_id_str
                })
                unique_results.add(key)
    return jsonify(final_results[:8])

@socketio.on('join')
def on_join(data):
    room = data['room']
    join_room(room)

@socketio.on('leave')
def on_leave(data):
    room = data['room']
    leave_room(room)

@socketio.on('connect')
def handle_connect():
    user_id = str(current_user.id) if current_user.is_authenticated else None
    if user_id:
        join_room(user_id)


# Real-time message seen event
@socketio.on('mark_seen')
def handle_mark_seen(data):
    from bson import ObjectId
    msg_id = data.get('msg_id')
    user_id = str(current_user.id)
    if not msg_id or not user_id:
        return
    # Mark message as seen in DB
    mongo.db.messages.update_one({'_id': ObjectId(msg_id)}, {'$set': {'seen': True}})
    # Emit seen event to both sender and receiver
    msg = mongo.db.messages.find_one({'_id': ObjectId(msg_id)})
    if msg:
        sender_id = str(msg['sender_id'])
        receiver_id = str(msg['receiver_id']) if msg.get('receiver_id') != 'global' else 'global'
        emit_data = {'msg_id': msg_id}
        socketio.emit('message_seen', emit_data, room=sender_id)
        if receiver_id != 'global':
            socketio.emit('message_seen', emit_data, room=receiver_id)

if __name__ == '__main__':
    socketio.run(app, debug=True)
