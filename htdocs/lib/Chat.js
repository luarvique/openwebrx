//
// Built-in Chat
//

function Chat() {}

// We start with these values
Chat.nickname = '';

// Load chat settings from local storage.
Chat.loadSettings = function() {
    this.setNickname(LS.has('chatname')? LS.loadStr('chatname') : '');
};

// Set chat nickname.
Chat.setNickname = function(nickname) {
    if (this.nickname !== nickname) {
        this.nickname = nickname;
        LS.save('chatname', nickname);
        $('#openwebrx-chat-name').val(nickname);
    }
};

Chat.recvMessage = function(nickname, text, color = 'white') {
    // Show chat panel
    toggle_panel('openwebrx-panel-log', true);

    divlog(
        Utils.HHMMSS(Date.now()) + '&nbsp;['
      + '<span class="chatname" style="color:' + color + ';">'
      + Utils.htmlEscape(nickname) + '</span>]:&nbsp;'
      + '<span class="chatmessage">' + Utils.htmlEscape(text)
      + '</span>'
    );
};

Chat.sendMessage = function(text, nickname = '') {
    ws.send(JSON.stringify({
        'type': 'sendmessage', 'name': nickname, 'text': text
    }));
};

// Collect nick and message from controls and send message.
Chat.send = function() {
    this.setNickname($('#openwebrx-chat-name').val().trim());

    var msg = $('#openwebrx-chat-message').val().trim();
    if (msg.length > 0) this.sendMessage(msg, this.nickname);
    $('#openwebrx-chat-message').val('');
};

// Attach events to chat controls.
Chat.keyPress = function(event) {
    if (event.key === 'Enter') {
        event.preventDefault();
        this.send();
    }
};
