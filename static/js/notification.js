// Real-time notification bell update for new messages
document.addEventListener('DOMContentLoaded', function() {
  var notifIcon = document.getElementById('topbar-notification-icon');
  var notifCount = document.getElementById('topbar-notification-count');
  if (typeof io === 'undefined') return;
  var socket = io();
  socket.on('new_message', function(data) {
    if (notifIcon) {
      notifIcon.classList.add('text-danger');
      notifIcon.setAttribute('title', 'New message!');
    }
    if (notifCount) {
      let count = parseInt(notifCount.textContent) || 0;
      notifCount.textContent = count + 1;
      notifCount.style.display = '';
    }
    // Also update Chat tab badge
    var chatTab = document.getElementById('chat-navbar-link');
    var chatBadge = document.getElementById('chat-navbar-badge');
    if (chatTab && chatBadge) {
      chatBadge.style.display = '';
      let badgeCount = parseInt(chatBadge.textContent) || 0;
      chatBadge.textContent = (badgeCount + 1) + ' New';
      chatTab.classList.add('text-danger');
      chatTab.setAttribute('title', 'New message!');
    }
  });
  // Optionally, reset notification on click
  if (notifIcon) {
    notifIcon.addEventListener('click', function() {
      notifIcon.classList.remove('text-danger');
      notifIcon.setAttribute('title', 'Notifications');
      if (notifCount) {
        notifCount.textContent = '';
        notifCount.style.display = 'none';
      }
    });
  }
  // Reset Chat tab badge on click
  var chatTab = document.getElementById('chat-navbar-link');
  var chatBadge = document.getElementById('chat-navbar-badge');
  if (chatTab && chatBadge) {
    chatTab.addEventListener('click', function() {
      chatTab.classList.remove('text-danger');
      chatTab.removeAttribute('title');
      chatBadge.style.display = 'none';
      chatBadge.textContent = '';
    });
  }
});
