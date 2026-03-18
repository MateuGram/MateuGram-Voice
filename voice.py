import os
import uuid
import time
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'voice-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*")

rooms = {}

def generate_room_id():
    return str(uuid.uuid4())[:8]

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/create')
def create_room():
    room_id = generate_room_id()
    rooms[room_id] = {
        'created_at': datetime.now(),
        'participants': {},
        'messages': []
    }
    return redirect(url_for('room', room_id=room_id))

@app.route('/room/<room_id>')
def room(room_id):
    if room_id not in rooms:
        return redirect(url_for('index'))
    return render_template_string(ROOM_HTML, room_id=room_id)

@app.route('/api/room/<room_id>')
def room_info(room_id):
    if room_id not in rooms:
        return jsonify({'error': 'Room not found'}), 404
    return jsonify({'participants': len(rooms[room_id]['participants'])})

# -------------------- Socket.IO --------------------
@socketio.on('join')
def handle_join(data):
    room_id = data['room_id']
    username = data.get('username', f'User_{uuid.uuid4().hex[:4]}')
    join_room(room_id)
    sid = request.sid
    rooms[room_id]['participants'][sid] = {
        'username': username,
        'joined_at': time.time()
    }
    emit('user_joined', {
        'sid': sid,
        'username': username,
        'participants': list(rooms[room_id]['participants'].values())
    }, room=room_id)
    participants_list = [{'sid': s, **p} for s, p in rooms[room_id]['participants'].items()]
    emit('existing_participants', {'participants': participants_list}, to=sid)
    emit('chat_history', {'messages': rooms[room_id]['messages']}, to=sid)

@socketio.on('leave')
def handle_leave(data):
    room_id = data['room_id']
    sid = request.sid
    leave_room(room_id)
    if room_id in rooms and sid in rooms[room_id]['participants']:
        username = rooms[room_id]['participants'][sid]['username']
        del rooms[room_id]['participants'][sid]
        emit('user_left', {'sid': sid, 'username': username}, room=room_id)

@socketio.on('offer')
def handle_offer(data):
    target_sid = data['target']
    emit('offer', {'offer': data['offer'], 'from': request.sid}, room=target_sid)

@socketio.on('answer')
def handle_answer(data):
    target_sid = data['target']
    emit('answer', {'answer': data['answer'], 'from': request.sid}, room=target_sid)

@socketio.on('ice-candidate')
def handle_ice(data):
    target_sid = data['target']
    emit('ice-candidate', {'candidate': data['candidate'], 'from': request.sid}, room=target_sid)

@socketio.on('chat-message')
def handle_chat_message(data):
    room_id = data['room_id']
    username = data['username']
    message = data['message']
    msg_data = {
        'username': username,
        'message': message,
        'time': datetime.now().strftime('%H:%M')
    }
    if room_id in rooms:
        rooms[room_id]['messages'].append(msg_data)
        if len(rooms[room_id]['messages']) > 100:
            rooms[room_id]['messages'] = rooms[room_id]['messages'][-100:]
    emit('new-chat-message', msg_data, room=room_id)

@socketio.on('screen-share')
def handle_screen_share(data):
    room_id = data['room_id']
    target_sid = data.get('target')
    if target_sid:
        emit('screen-share-offer', {
            'offer': data['offer'],
            'from': request.sid
        }, room=target_sid)
    else:
        emit('screen-share-started', {'sid': request.sid}, room=room_id, include_self=False)

@socketio.on('screen-share-answer')
def handle_screen_share_answer(data):
    target_sid = data['target']
    emit('screen-share-answer', {'answer': data['answer'], 'from': request.sid}, room=target_sid)

@socketio.on('disconnect')
def handle_disconnect():
    for room_id, room_data in list(rooms.items()):
        if request.sid in room_data['participants']:
            username = room_data['participants'][request.sid]['username']
            del room_data['participants'][request.sid]
            emit('user_left', {'sid': request.sid, 'username': username}, room=room_id)
            break

# -------------------- Шаблоны --------------------
INDEX_HTML = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MateuGram Voice</title>
    <link rel="icon" type="image/png" href="https://mateugram.onrender.com/photos/logo.png">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', system-ui, sans-serif; }
        body {
            background: linear-gradient(145deg, #0b2b5c, #2c6b9e);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 30px;
            padding: 40px;
            max-width: 500px;
            width: 100%;
            box-shadow: 0 30px 60px rgba(0,0,0,0.3);
            text-align: center;
        }
        h1 {
            background: linear-gradient(145deg, #0b2b5c, #2c6b9e);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 20px;
            font-size: 2.5em;
        }
        p { color: #4a5568; margin-bottom: 30px; font-size: 1.1em; }
        .btn {
            display: inline-block;
            background: linear-gradient(145deg, #0b2b5c, #2c6b9e);
            color: white;
            padding: 14px 32px;
            border-radius: 40px;
            text-decoration: none;
            margin: 8px;
            font-weight: 600;
            border: none;
            cursor: pointer;
            font-size: 16px;
            transition: 0.3s;
        }
        .btn:hover { transform: translateY(-2px); box-shadow: 0 8px 15px rgba(11,43,92,0.3); }
        .btn-outline {
            background: transparent;
            border: 2px solid #2c6b9e;
            color: #2c6b9e;
        }
        input {
            width: 100%;
            padding: 14px 18px;
            border: 2px solid #e2e8f0;
            border-radius: 30px;
            font-size: 16px;
            margin-bottom: 20px;
            outline: none;
        }
        input:focus { border-color: #2c6b9e; }
        .link { margin-top: 20px; }
        .link a { color: #2c6b9e; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <h1>MateuGram Voice</h1>
        <p>Бесплатные видеозвонки без ограничений</p>
        
        <a href="/create" class="btn">Создать конференцию</a>
        
        <div style="margin-top: 30px;">
            <p style="margin-bottom: 10px;">Или введите код комнаты:</p>
            <form onsubmit="event.preventDefault(); window.location.href='/room/' + document.getElementById('room-id').value;">
                <input type="text" id="room-id" placeholder="Код комнаты" required>
                <button type="submit" class="btn btn-outline">Присоединиться</button>
            </form>
        </div>
        <div class="link"><a href="https://mateugram.onrender.com">← Вернуться в MateuGram</a></div>
    </div>
</body>
</html>
'''

ROOM_HTML = '''<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Комната {{ room_id }} | MateuGram Voice</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <link rel="icon" type="image/png" href="https://mateugram.onrender.com/photos/logo.png">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', system-ui, sans-serif; }
        body {
            background: linear-gradient(145deg, #0b2b5c, #2c6b9e);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        .header {
            background: white;
            border-radius: 20px;
            padding: 15px 25px;
            margin-bottom: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 10px;
        }
        .room-info h2 { color: #0b2b5c; font-size: 1.3em; }
        .room-info p { color: #2c6b9e; font-weight: 600; }
        .controls { display: flex; gap: 10px; flex-wrap: wrap; }
        .btn {
            background: linear-gradient(145deg, #0b2b5c, #2c6b9e);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 30px;
            cursor: pointer;
            font-weight: 600;
            transition: 0.2s;
        }
        .btn-outline {
            background: white;
            color: #2c6b9e;
            border: 2px solid #2c6b9e;
        }
        .btn-danger { background: #dc3545; }
        .btn-success { background: #28a745; }
        .btn:hover { transform: scale(1.05); }
        .videos-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .video-container {
            background: white;
            border-radius: 20px;
            padding: 15px;
            box-shadow: 0 10px 20px rgba(0,0,0,0.2);
            position: relative;
        }
        .video-container video {
            width: 100%;
            border-radius: 15px;
            background: #000;
        }
        .participant-info {
            position: absolute;
            bottom: 25px;
            left: 25px;
            background: rgba(0,0,0,0.5);
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 14px;
        }
        .chat-section {
            background: white;
            border-radius: 20px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            height: 300px;
        }
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            margin-bottom: 15px;
            padding: 10px;
            background: #f8fafc;
            border-radius: 15px;
        }
        .message {
            margin-bottom: 10px;
            padding: 8px 12px;
            border-radius: 18px;
            max-width: 80%;
        }
        .message.own {
            background: linear-gradient(145deg, #0b2b5c, #2c6b9e);
            color: white;
            margin-left: auto;
        }
        .message.other {
            background: #e2e8f0;
            color: #1a202c;
        }
        .message .sender { font-size: 12px; font-weight: bold; margin-bottom: 3px; }
        .message .time { font-size: 10px; text-align: right; margin-top: 3px; opacity: 0.7; }
        .chat-input { display: flex; gap: 10px; }
        .chat-input input {
            flex: 1;
            padding: 12px;
            border: 2px solid #e2e8f0;
            border-radius: 30px;
            outline: none;
        }
        .chat-input button {
            background: #2c6b9e;
            color: white;
            border: none;
            padding: 0 20px;
            border-radius: 30px;
            cursor: pointer;
        }
        .back-link { margin-top: 10px; text-align: center; }
        .back-link a { color: white; text-decoration: none; }
        .error-message {
            background: #dc3545;
            color: white;
            padding: 10px;
            border-radius: 5px;
            margin: 10px 0;
            text-align: center;
        }
        .permission-request {
            background: #e6f0fa;
            padding: 20px;
            border-radius: 15px;
            margin: 20px 0;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="room-info">
                <h2>Комната {{ room_id }}</h2>
                <p id="participant-count">Участников: 1</p>
            </div>
            <div class="controls">
                <button id="mic-btn" class="btn btn-outline" disabled>🎤 Микрофон</button>
                <button id="cam-btn" class="btn btn-outline" disabled>📷 Камера</button>
                <button id="screen-btn" class="btn btn-outline" disabled>🖥️ Экран</button>
                <button id="leave-btn" class="btn btn-danger">Покинуть</button>
            </div>
        </div>

        <div id="media-error" class="error-message" style="display: none;"></div>
        <div id="permission-request" class="permission-request" style="display: none;">
            <p>Для участия в звонке нужен доступ к камере и микрофону.</p>
            <button id="request-permission-btn" class="btn btn-success">Разрешить доступ</button>
        </div>

        <div class="videos-grid" id="videos-grid"></div>

        <div class="chat-section">
            <div class="chat-messages" id="chat-messages"></div>
            <div class="chat-input">
                <input type="text" id="chat-input" placeholder="Напишите сообщение...">
                <button id="send-chat">➤</button>
            </div>
        </div>
        <div class="back-link"><a href="https://mateugram.onrender.com">← Вернуться в MateuGram</a></div>
    </div>

    <script>
        const roomId = '{{ room_id }}';
        const socket = io();
        const participants = {};  // все участники (sid -> данные)
        let localStream = null;
        let username = 'User_' + Math.random().toString(36).substr(2, 4);
        let micEnabled = true;
        let camEnabled = true;
        let screenStream = null;
        let screenSharing = false;

        const peerConnections = {};  // pc для каждого удалённого участника
        const pendingParticipants = []; // участники, которые вошли до получения потока

        socket.emit('join', { room_id: roomId, username: username });

        socket.on('existing_participants', (data) => {
            data.participants.forEach(p => {
                participants[p.sid] = p;
                // Если поток уже есть, сразу создаём pc
                if (localStream) {
                    createPeerConnection(p.sid, true);
                } else {
                    // Иначе добавляем в ожидающие
                    pendingParticipants.push(p.sid);
                }
            });
            updateParticipantsCount();
        });

        socket.on('user_joined', (data) => {
            participants[data.sid] = { sid: data.sid, username: data.username };
            if (localStream) {
                createPeerConnection(data.sid, true);
            } else {
                pendingParticipants.push(data.sid);
            }
            updateParticipantsCount();
            addChatMessage({ username: 'System', message: `${data.username} присоединился(лась)` });
        });

        socket.on('user_left', (data) => {
            if (participants[data.sid]) {
                delete participants[data.sid];
                if (peerConnections[data.sid]) {
                    peerConnections[data.sid].close();
                    delete peerConnections[data.sid];
                }
                removeVideoElement(data.sid);
                updateParticipantsCount();
                addChatMessage({ username: 'System', message: `${data.username} покинул(а)` });
            }
        });

        socket.on('offer', async (data) => {
            // Создаём pc для того, кто прислал offer, если его ещё нет
            if (!peerConnections[data.from]) {
                createPeerConnection(data.from, false);
            }
            const pc = peerConnections[data.from];
            await pc.setRemoteDescription(new RTCSessionDescription(data.offer));
            const answer = await pc.createAnswer();
            await pc.setLocalDescription(answer);
            socket.emit('answer', { target: data.from, answer: answer });
        });

        socket.on('answer', async (data) => {
            const pc = peerConnections[data.from];
            if (pc) {
                await pc.setRemoteDescription(new RTCSessionDescription(data.answer));
            }
        });

        socket.on('ice-candidate', async (data) => {
            const pc = peerConnections[data.from];
            if (pc) {
                await pc.addIceCandidate(new RTCIceCandidate(data.candidate));
            }
        });

        // Создаёт peerConnection для указанного участника
        function createPeerConnection(targetSid, initiator) {
            if (peerConnections[targetSid]) return peerConnections[targetSid];

            const pc = new RTCPeerConnection({
                iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
            });

            pc.onicecandidate = (event) => {
                if (event.candidate) {
                    socket.emit('ice-candidate', { target: targetSid, candidate: event.candidate });
                }
            };

            pc.ontrack = (event) => {
                const [remoteStream] = event.streams;
                displayRemoteVideo(targetSid, remoteStream);
            };

            // Если у нас уже есть локальный поток, добавляем его треки
            if (localStream) {
                localStream.getTracks().forEach(track => {
                    pc.addTrack(track, localStream);
                });
            }

            peerConnections[targetSid] = pc;

            if (initiator) {
                pc.createOffer()
                    .then(offer => pc.setLocalDescription(offer))
                    .then(() => {
                        socket.emit('offer', { target: targetSid, offer: pc.localDescription });
                    });
            }

            return pc;
        }

        // Запрос доступа к медиа (вызывается по кнопке)
        async function requestMediaAccess() {
            try {
                localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
                displayLocalVideo(localStream);

                // Создаём pc для всех ожидающих участников
                pendingParticipants.forEach(sid => {
                    if (!peerConnections[sid]) {
                        createPeerConnection(sid, true);
                    }
                });
                // Очищаем список ожидающих
                pendingParticipants.length = 0;

                // Активируем кнопки
                document.getElementById('mic-btn').disabled = false;
                document.getElementById('cam-btn').disabled = false;
                document.getElementById('screen-btn').disabled = false;
                document.getElementById('permission-request').style.display = 'none';
            } catch (err) {
                console.error('Ошибка доступа к медиа:', err);
                document.getElementById('media-error').style.display = 'block';
                document.getElementById('media-error').textContent = 'Не удалось получить доступ к камере/микрофону. Проверьте разрешения.';
                document.getElementById('permission-request').style.display = 'block';
            }
        }

        function displayLocalVideo(stream) {
            const videoContainer = document.createElement('div');
            videoContainer.className = 'video-container';
            videoContainer.id = `video-${socket.id}`;
            const video = document.createElement('video');
            video.srcObject = stream;
            video.autoplay = true;
            video.muted = true;
            video.playsInline = true;
            videoContainer.appendChild(video);
            const info = document.createElement('div');
            info.className = 'participant-info';
            info.textContent = `${username} (Вы)`;
            videoContainer.appendChild(info);
            document.getElementById('videos-grid').appendChild(videoContainer);
        }

        function displayRemoteVideo(sid, stream) {
            if (document.getElementById(`video-${sid}`)) return;
            const videoContainer = document.createElement('div');
            videoContainer.className = 'video-container';
            videoContainer.id = `video-${sid}`;
            const video = document.createElement('video');
            video.srcObject = stream;
            video.autoplay = true;
            video.playsInline = true;
            videoContainer.appendChild(video);
            const info = document.createElement('div');
            info.className = 'participant-info';
            info.textContent = participants[sid]?.username || 'User';
            videoContainer.appendChild(info);
            document.getElementById('videos-grid').appendChild(videoContainer);
        }

        function removeVideoElement(sid) {
            const el = document.getElementById(`video-${sid}`);
            if (el) el.remove();
        }

        function updateParticipantsCount() {
            document.getElementById('participant-count').textContent = `Участников: ${Object.keys(participants).length + 1}`;
        }

        // Чат
        socket.on('chat_history', (data) => {
            data.messages.forEach(msg => addChatMessage(msg));
        });

        socket.on('new-chat-message', (data) => {
            addChatMessage(data);
        });

        function addChatMessage(data) {
            const messagesDiv = document.getElementById('chat-messages');
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${data.username === username ? 'own' : 'other'}`;
            if (data.username !== username && data.username !== 'System') {
                const senderDiv = document.createElement('div');
                senderDiv.className = 'sender';
                senderDiv.textContent = data.username;
                msgDiv.appendChild(senderDiv);
            }
            const contentDiv = document.createElement('div');
            contentDiv.textContent = data.message;
            msgDiv.appendChild(contentDiv);
            if (data.time) {
                const timeDiv = document.createElement('div');
                timeDiv.className = 'time';
                timeDiv.textContent = data.time;
                msgDiv.appendChild(timeDiv);
            }
            messagesDiv.appendChild(msgDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }

        document.getElementById('send-chat').onclick = sendChat;
        document.getElementById('chat-input').onkeypress = (e) => {
            if (e.key === 'Enter') sendChat();
        };

        function sendChat() {
            const input = document.getElementById('chat-input');
            const text = input.value.trim();
            if (text) {
                socket.emit('chat-message', {
                    room_id: roomId,
                    username: username,
                    message: text
                });
                input.value = '';
            }
        }

        // Кнопки управления
        document.getElementById('mic-btn').onclick = () => {
            if (localStream) {
                const audioTrack = localStream.getAudioTracks()[0];
                if (audioTrack) {
                    audioTrack.enabled = !audioTrack.enabled;
                    document.getElementById('mic-btn').textContent = audioTrack.enabled ? '🎤 Микрофон' : '🔇 Микрофон';
                }
            }
        };

        document.getElementById('cam-btn').onclick = () => {
            if (localStream) {
                const videoTrack = localStream.getVideoTracks()[0];
                if (videoTrack) {
                    videoTrack.enabled = !videoTrack.enabled;
                    document.getElementById('cam-btn').textContent = videoTrack.enabled ? '📷 Камера' : '🚫 Камера';
                }
            }
        };

        document.getElementById('screen-btn').onclick = shareScreen;

        async function shareScreen() {
            if (screenSharing) {
                screenStream.getTracks().forEach(t => t.stop());
                screenSharing = false;
                const newStream = await navigator.mediaDevices.getUserMedia({ video: true });
                const videoTrack = newStream.getVideoTracks()[0];
                localStream.addTrack(videoTrack);
                Object.values(peerConnections).forEach(pc => {
                    const sender = pc.getSenders().find(s => s.track.kind === 'video');
                    if (sender) sender.replaceTrack(videoTrack);
                });
            } else {
                try {
                    screenStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
                    screenSharing = true;
                    const videoTrack = screenStream.getVideoTracks()[0];
                    localStream.addTrack(videoTrack);
                    Object.values(peerConnections).forEach(pc => {
                        const sender = pc.getSenders().find(s => s.track.kind === 'video');
                        if (sender) sender.replaceTrack(videoTrack);
                    });
                } catch (err) {
                    console.error(err);
                }
            }
        }

        document.getElementById('leave-btn').onclick = () => {
            socket.emit('leave', { room_id: roomId });
            window.location.href = '/';
        };

        // Показываем запрос разрешения
        document.getElementById('permission-request').style.display = 'block';
        document.getElementById('request-permission-btn').onclick = requestMediaAccess;

        window.onbeforeunload = () => {
            socket.emit('leave', { room_id: roomId });
        };
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
