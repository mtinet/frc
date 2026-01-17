"""
FRC Display Controller
화면 출력기 메인 애플리케이션
"""
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)  # CORS 지원 추가
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

# 업로드 폴더 생성
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'images'), exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'videos'), exist_ok=True)

# 상태 저장 (메모리 기반, 필요시 파일로 저장 가능)
state = {
    'score': {
        'team1': 0,
        'team2': 0,
        'team1_name': 'Team 1',
        'team2_name': 'Team 2'
    },
    'preview_media': {  # 미리보기 (컷 전)
        'type': None,  # 'youtube', 'image', 'video', 'none'
        'url': None,
        'youtube_id': None,
        'filename': None
    },
    'current_media': {  # 프로그램 뷰 (뷰박스에 표시되는 것)
        'type': None,
        'url': None,
        'youtube_id': None,
        'filename': None
    },
    'layout': 'default',
    'viewbox_resolution': {
        'width': None,
        'height': None
    }
}

@app.route('/')
def control_panel():
    """컨트롤 박스 메인 페이지"""
    return render_template('control.html')

@app.route('/view')
def view_box():
    """뷰박스 전용 페이지 (별도 모니터용)"""
    return render_template('view.html')

@app.route('/api/report-resolution', methods=['POST'])
def report_resolution():
    """뷰박스 해상도 보고"""
    global state
    data = request.json or {}
    width = data.get('width')
    height = data.get('height')

    if width is not None and height is not None:
        state['viewbox_resolution']['width'] = width
        state['viewbox_resolution']['height'] = height
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': 'Width and height required'}), 400

@app.route('/api/state', methods=['GET'])
def get_state():
    """현재 상태 조회"""
    return jsonify(state)

@app.route('/api/state', methods=['POST'])
def update_state():
    """상태 업데이트"""
    global state
    data = request.json or {}
    
    if 'score' in data:
        state['score'].update(data['score'])
    
    if 'current_media' in data:
        state['current_media'].update(data['current_media'])
    
    if 'layout' in data:
        state['layout'] = data['layout']
    
    return jsonify(state)  # 상태 객체 전체 반환

@app.route('/api/youtube', methods=['POST'])
def set_youtube():
    """유튜브 URL 설정 (미리보기에 설정)"""
    global state
    data = request.json or {}
    youtube_url = data.get('url', '')
    
    # YouTube URL에서 video ID 추출
    youtube_id = None
    if 'youtube.com/watch?v=' in youtube_url:
        youtube_id = youtube_url.split('youtube.com/watch?v=')[1].split('&')[0]
    elif 'youtu.be/' in youtube_url:
        youtube_id = youtube_url.split('youtu.be/')[1].split('?')[0]
    
    if youtube_id:
        state['preview_media'] = {
            'type': 'youtube',
            'url': youtube_url,
            'youtube_id': youtube_id,
            'filename': None
        }
        return jsonify({'status': 'success', 'youtube_id': youtube_id})
    else:
        return jsonify({'status': 'error', 'message': 'Invalid YouTube URL'}), 400

@app.route('/api/clear-media', methods=['POST'])
def clear_media():
    """미디어 클리어"""
    global state
    target = request.json.get('target', 'current')  # 'preview' or 'current'
    if target == 'preview':
        state['preview_media'] = {
            'type': None,
            'url': None,
            'youtube_id': None,
            'filename': None
        }
    else:
        state['current_media'] = {
            'type': None,
            'url': None,
            'youtube_id': None,
            'filename': None
        }
    return jsonify({'status': 'success'})

@app.route('/api/preview-media', methods=['POST'])
def set_preview_media():
    """미리보기 미디어 설정"""
    global state
    data = request.json or {}
    media_type = data.get('type')
    
    if media_type == 'youtube':
        youtube_url = data.get('url', '')
        youtube_id = None
        if 'youtube.com/watch?v=' in youtube_url:
            youtube_id = youtube_url.split('youtube.com/watch?v=')[1].split('&')[0]
        elif 'youtu.be/' in youtube_url:
            youtube_id = youtube_url.split('youtu.be/')[1].split('?')[0]
        
        if youtube_id:
            state['preview_media'] = {
                'type': 'youtube',
                'url': youtube_url,
                'youtube_id': youtube_id,
                'filename': None
            }
            return jsonify({'status': 'success', 'youtube_id': youtube_id})
        else:
            return jsonify({'status': 'error', 'message': 'Invalid YouTube URL'}), 400
    
    elif media_type == 'image' or media_type == 'video':
        filename = data.get('filename')
        if filename:
            state['preview_media'] = {
                'type': media_type,
                'url': f'/uploads/{media_type}s/{filename}',
                'youtube_id': None,
                'filename': filename
            }
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': 'Filename required'}), 400
    
    return jsonify({'status': 'error', 'message': 'Invalid media type'}), 400

@app.route('/api/cut', methods=['POST'])
def cut_to_program():
    """미리보기를 프로그램 뷰로 전송 (컷)"""
    global state
    state['current_media'] = state['preview_media'].copy()
    return jsonify({'status': 'success', 'media': state['current_media']})

@app.route('/api/files', methods=['GET'])
def list_files():
    """파일 목록 조회"""
    media_type = request.args.get('type', 'all')  # 'images', 'videos', 'all'
    files = []
    
    if media_type in ['images', 'all']:
        images_path = os.path.join(app.config['UPLOAD_FOLDER'], 'images')
        if os.path.exists(images_path):
            for filename in os.listdir(images_path):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    filepath = os.path.join(images_path, filename)
                    files.append({
                        'type': 'image',
                        'filename': filename,
                        'url': f'/uploads/images/{filename}',
                        'size': os.path.getsize(filepath)
                    })
    
    if media_type in ['videos', 'all']:
        videos_path = os.path.join(app.config['UPLOAD_FOLDER'], 'videos')
        if os.path.exists(videos_path):
            for filename in os.listdir(videos_path):
                if filename.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm')):
                    filepath = os.path.join(videos_path, filename)
                    files.append({
                        'type': 'video',
                        'filename': filename,
                        'url': f'/uploads/videos/{filename}',
                        'size': os.path.getsize(filepath)
                    })
    
    return jsonify({'files': files})

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """업로드된 파일 제공"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    print("=" * 50)
    print("FRC Display Controller 시작")
    print("=" * 50)
    print("컨트롤 박스: http://localhost:8080")
    print("뷰박스 (별도 모니터): http://localhost:8080/view")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=8080)
