document.addEventListener('DOMContentLoaded', function() {
  if (typeof io === 'undefined') {
    alert('Socket.IO client library not loaded. Please check your internet connection or script tag.');
    return;
  }
  var socket = io();
  // Real-time message deletion
  socket.on('delete_message', function(data) {
      var msgId = data.msg_id;
      var chatBox = document.getElementById('chat-box');
      var bubbles = chatBox.querySelectorAll('.delete-msg[data-msgid="' + msgId + '"]');
      bubbles.forEach(function(btn) {
          if (btn.parentElement) btn.parentElement.parentElement.remove();
      });
  });
  var chatForm = document.getElementById('chat-form');
  var chatInput = document.getElementById('chat-input');
  var chatBox = document.getElementById('chat-box');
  var userList = document.getElementById('user-list');
  var chatOptions = document.getElementById('chat-options');
  var notificationArea = document.getElementById('notification-area');
  var chatHeader = document.getElementById('chat-header');
  var deleteBtn = document.getElementById('delete-conversation');
  var selectedUser = null;
  var selectedUserId = null;
  var isGlobal = false;
  var currentUserId = window.currentUserId || document.body.getAttribute('data-userid');

  function setChatHeader() {
      if (isGlobal) {
          chatHeader.textContent = 'Global Chat (Everyone)';
          if (deleteBtn) deleteBtn.style.display = 'none';
      } else if (selectedUser) {
          chatHeader.textContent = 'Chat with ' + selectedUser;
          if (deleteBtn) deleteBtn.style.display = 'inline-block';
      } else {
          chatHeader.textContent = '';
          if (deleteBtn) deleteBtn.style.display = 'none';
      }
  }

  if (chatOptions) {
      chatOptions.addEventListener('click', function(e) {
          var target = e.target.closest('.user-item');
          if (target && target.getAttribute('data-userid') === 'global') {
              document.querySelectorAll('.user-item').forEach(function(item) {
                  item.classList.remove('active');
                  item.style.background = '';
                  item.style.color = '';
              });
              target.classList.add('active');
              target.style.background = 'linear-gradient(90deg, #6a11cb 0%, #2575fc 100%)';
              target.style.color = '#fff';
              isGlobal = true;
              selectedUser = 'Global';
              selectedUserId = null;
              chatBox.innerHTML = '';
              notificationArea.innerHTML = '';
              setChatHeader();
              socket.emit('join', { room: 'global' });
              fetch('/chat/global_history')
                  .then(res => res.json())
                  .then(data => {
                      chatBox.innerHTML = '';
                      data.messages.forEach(function(msg) {
                          chatBox.innerHTML += `<div><b>${msg.sender_username || msg.sender || 'Unknown'}:</b> ${msg.content}</div>`;
                      });
                  });
          }
      });
  }

  if (userList) {
    userList.addEventListener('click', function(e) {
      var target = e.target.closest('.user-item');
      if (target) {
          if (e.target.tagName === 'BUTTON' && e.target.closest('form')) {
              return;
          }
          document.querySelectorAll('.user-item').forEach(function(item) {
              item.classList.remove('active');
              item.style.background = '';
              item.style.color = '';
          });
          target.classList.add('active');
          target.style.background = 'linear-gradient(90deg, #6a11cb 0%, #2575fc 100%)';
          target.style.color = '#fff';

          isGlobal = false;
          selectedUser = target.getAttribute('data-username');
          selectedUserId = target.getAttribute('data-userid');
          chatBox.innerHTML = '';
          notificationArea.innerHTML = '';
          setChatHeader();
          socket.emit('join', { room: selectedUser });
          fetch(`/chat/history/${selectedUserId}`)
              .then(res => res.json())
              .then(data => {
                  renderMessages(data.messages);
              });
      }
    });
  }

  function renderMessages(messages) {
      chatBox.innerHTML = '';
      if (!messages || messages.length === 0) {
          chatBox.innerHTML = `<div class='text-center text-muted mt-5'>No messages yet. Start the conversation!</div>`;
          return;
      }
      messages.forEach(function(msg) {
          var isMine = (String(msg.sender_id) === String(currentUserId));
          var senderName = msg.sender_username || (isMine ? 'You' : selectedUser);
          var align = isMine ? 'justify-content-end' : 'justify-content-start';
          var bubbleColor = isMine ? 'bg-primary text-white' : 'bg-white border';
          var deleteBtn = isMine ? `<button class='btn btn-sm btn-link text-danger delete-msg' data-msgid='${msg._id||""}' title='Delete'><i class='bi bi-trash'></i></button>` : '';
          var seenText = msg.seen ? "<span class='text-success ms-2' style='font-size:0.8em;'>Seen</span>" : "";
          var time = msg.timestamp ? `<span class='text-muted ms-2' style='font-size:0.8em;'>${new Date(msg.timestamp).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</span>` : '';
          chatBox.innerHTML += `<div class='d-flex ${align} mb-2'>
              <div class='p-2 ${bubbleColor}' style='border-radius:16px; max-width:70%; position:relative;'>
                  <div style='font-weight:bold;'>${senderName} ${time}</div>
                  <div>${msg.content} ${deleteBtn} ${seenText}</div>
              </div>
          </div>`;
      });
      chatBox.scrollTop = chatBox.scrollHeight;
  }

  if (chatForm) {
      chatForm.addEventListener('submit', function(e) {
          e.preventDefault();
          if (chatInput.value && (selectedUser || isGlobal)) {
              socket.emit('send_message', {
                  receiver: selectedUser,
                  receiver_id: selectedUserId,
                  content: chatInput.value,
                  is_global: isGlobal
              });
              chatInput.value = '';
          }
      });
  }

  if (deleteBtn) {
      deleteBtn.addEventListener('click', function() {
          if (selectedUserId) {
              fetch(`/chat/conversation/${selectedUserId}/delete`, { method: 'POST' })
                  .then(res => res.json())
                  .then(data => {
                      if (data.status === 'success') {
                          chatBox.innerHTML = '';
                      }
                  });
          }
      });
  }

  chatBox.addEventListener('click', function(e) {
      var btn = e.target.closest('.delete-msg');
      if (btn) {
          var msgId = btn.getAttribute('data-msgid');
          if (msgId) {
              fetch(`/chat/message/${msgId}/delete`, { method: 'POST' })
                  .then(res => res.json())
                  .then(data => {
                      if (data.status === 'success') {
                          btn.parentElement.remove();
                      }
                  });
          }
      }
  });

  socket.on('receive_message', function(data) {
      var isMine = (data.sender_id === currentUserId);
      var senderName = data.sender_username || (isMine ? 'You' : data.sender);
      var align = isMine ? 'justify-content-end' : 'justify-content-start';
      var bubbleColor = isMine ? 'bg-primary text-white' : 'bg-white border';
      var deleteBtn = isMine ? `<button class='btn btn-sm btn-link text-danger delete-msg' data-msgid='${data._id||""}' title='Delete'><i class='bi bi-trash'></i></button>` : '';
      var seenText = data.seen ? "<span class='text-success ms-2' style='font-size:0.8em;'>Seen</span>" : "";
      var time = data.timestamp ? `<span class='text-muted ms-2' style='font-size:0.8em;'>${new Date(data.timestamp).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</span>` : '';
      chatBox.innerHTML += `<div class='d-flex ${align} mb-2'>
          <div class='p-2 ${bubbleColor}' style='border-radius:16px; max-width:70%; position:relative;'>
              <div style='font-weight:bold;'>${senderName} ${time}</div>
              <div>${data.content} ${deleteBtn} ${seenText}</div>
          </div>
      </div>`;
      chatBox.scrollTop = chatBox.scrollHeight;
      if (data.notification) {
          notificationArea.innerHTML = `<div class='alert alert-info'>${data.notification}</div>`;
          setTimeout(function() { notificationArea.innerHTML = ''; }, 4000);
      }
  });

  // Notification bell update and dropdown (moved to notification.js)
});
