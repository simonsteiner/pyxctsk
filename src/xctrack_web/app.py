"""Flask web application for XCTrack task visualization."""

import base64
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict, Any

try:
    from flask import Flask, render_template, request, jsonify
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

try:
    from xctrack import parse_task, Task, calculate_task_distances
    from xctrack.utils import generate_qr_code, QR_CODE_SUPPORT
    XCTRACK_AVAILABLE = True
except ImportError:
    XCTRACK_AVAILABLE = False


class XCTrackWebApp:
    """Web application for XCTrack task visualization."""
    
    def __init__(self, debug: bool = False, tasks_dir: Optional[str] = None):
        """Initialize the web application.
        
        Args:
            debug: Enable Flask debug mode
            tasks_dir: Directory containing task files
        """
        if not FLASK_AVAILABLE:
            raise ImportError("Flask is required for the web interface. Install with: pip install flask")
        
        if not XCTRACK_AVAILABLE:
            raise ImportError("XCTrack core module is required. Install with: pip install ../xctrack")
        
        self.app = Flask(__name__, 
                        template_folder=str(Path(__file__).parent / 'templates'),
                        static_folder=str(Path(__file__).parent / 'static'))
        self.app.config['DEBUG'] = debug
        
        # Set default task directory
        if tasks_dir:
            self.task_directory = Path(tasks_dir)
        else:
            # Default to tests directory in the parent project
            self.task_directory = Path(__file__).parent.parent.parent / 'tests'
        
        self.setup_routes()
    
    def setup_routes(self):
        """Setup Flask routes."""
        
        @self.app.route('/')
        def index():
            """Main page."""
            return render_template('index.html')
        
        @self.app.route('/task/<task_code>')
        def view_task(task_code: str):
            """View a task by code."""
            return render_template('task.html', task_code=task_code)
        
        @self.app.route('/api/task/<task_code>')
        def api_get_task(task_code: str):
            """API endpoint to get task data."""
            try:
                # Try to load the task file
                task_file = self._find_task_file(task_code)
                
                if task_file and task_file.exists():
                    with open(task_file, 'r') as f:
                        task_data = f.read()
                    task = parse_task(task_data)
                    return jsonify(self._task_to_dict(task))
                else:
                    return jsonify({'error': 'Task not found'}), 404
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/task/<task_code>/qr')
        def api_get_qr_code(task_code: str):
            """API endpoint to get QR code for a task."""
            try:
                if not QR_CODE_SUPPORT:
                    return jsonify({'error': 'QR code support not available'}), 500
                
                # Load task
                task_file = self._find_task_file(task_code)
                
                if task_file and task_file.exists():
                    with open(task_file, 'r') as f:
                        task_data = f.read()
                    task = parse_task(task_data)
                    
                    # Generate QR code
                    qr_task = task.to_qr_code_task()
                    qr_string = qr_task.to_string()
                    qr_image = generate_qr_code(qr_string, size=512)
                    
                    # Convert to base64
                    img_buffer = BytesIO()
                    qr_image.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    img_b64 = base64.b64encode(img_buffer.getvalue()).decode()
                    
                    return jsonify({
                        'qr_code': f'data:image/png;base64,{img_b64}',
                        'qr_string': qr_string
                    })
                else:
                    return jsonify({'error': 'Task not found'}), 404
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/upload', methods=['POST'])
        def upload_task():
            """Upload and parse a task file."""
            try:
                if 'file' not in request.files:
                    return jsonify({'error': 'No file uploaded'}), 400
                
                file = request.files['file']
                if file.filename == '':
                    return jsonify({'error': 'No file selected'}), 400
                
                # Parse the uploaded task
                task_data = file.read()
                task = parse_task(task_data)
                
                return jsonify(self._task_to_dict(task))
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/tasks')
        def api_list_tasks():
            """API endpoint to list available tasks."""
            try:
                tasks = []
                if self.task_directory.exists():
                    for task_file in self.task_directory.glob('*.xctsk'):
                        try:
                            with open(task_file, 'r') as f:
                                task_data = f.read()
                            task = parse_task(task_data)
                            task_dict = self._task_to_dict(task)
                            tasks.append({
                                'code': task_file.stem.replace('task_', ''),
                                'name': f"Task {task_file.stem}",
                                'distance': task_dict['stats']['totalDistance'],
                                'optimizedDistance': task_dict['stats']['totalOptimizedDistance'],
                                'savings': task_dict['stats']['optimizationSavings'],
                                'savingsPercent': task_dict['stats']['optimizationSavingsPercent'],
                                'turnpoints': task_dict['stats']['turnpointCount'],
                                'cylinders': task_dict['stats']['cylinderCount'],
                                'type': task_dict['taskType']
                            })
                        except Exception:
                            continue
                return jsonify({'tasks': tasks})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
    
    def _find_task_file(self, task_code: str) -> Optional[Path]:
        """Find a task file by code."""
        # Try different naming patterns
        patterns = [
            f'task_{task_code}.xctsk',
            f'{task_code}.xctsk',
            'task_meta.xctsk' if task_code == 'meta' else None
        ]
        
        for pattern in patterns:
            if pattern:
                task_file = self.task_directory / pattern
                if task_file.exists():
                    return task_file
        
        return None
    
    def _task_to_dict(self, task: Task) -> Dict[str, Any]:
        """Convert a task to a dictionary for JSON serialization."""
        result = {
            'taskType': task.task_type.value,
            'version': task.version,
            'earthModel': task.earth_model.value if task.earth_model else None,
            'turnpoints': [],
            'stats': {}
        }
        
        # Calculate optimized distances using the new distance calculator
        distance_data = calculate_task_distances(task)
        
        # Add turnpoint data with both basic and optimized distances
        for i, tp in enumerate(task.turnpoints):
            tp_distance_data = distance_data['turnpoints'][i] if i < len(distance_data['turnpoints']) else {}
            
            tp_data = {
                'index': i,
                'name': tp.waypoint.name,
                'description': tp.waypoint.description or '',
                'lat': tp.waypoint.lat,
                'lon': tp.waypoint.lon,
                'alt': tp.waypoint.alt_smoothed,
                'radius': tp.radius,
                'type': tp.type.value if tp.type else '',
                'distance': 0,  # Distance from previous turnpoint (basic calculation)
                'cumulative_distance': tp_distance_data.get('cumulative_center_km', 0),
                'cumulative_optimized_distance': tp_distance_data.get('cumulative_optimized_km', 0)
            }
            
            # Calculate basic distance from previous turnpoint for compatibility
            if i > 0:
                prev_tp = task.turnpoints[i-1]
                distance = self._calculate_distance(
                    prev_tp.waypoint.lat, prev_tp.waypoint.lon,
                    tp.waypoint.lat, tp.waypoint.lon
                )
                tp_data['distance'] = round(distance, 1)
            
            result['turnpoints'].append(tp_data)
        
        # Add task configuration
        if task.takeoff:
            result['takeoff'] = {
                'timeOpen': str(task.takeoff.time_open) if task.takeoff.time_open else None,
                'timeClose': str(task.takeoff.time_close) if task.takeoff.time_close else None
            }
        
        if task.sss:
            result['sss'] = {
                'type': task.sss.type.value,
                'direction': task.sss.direction.value,
                'timeGates': [str(gate) for gate in task.sss.time_gates],
                'timeClose': str(task.sss.time_close) if task.sss.time_close else None
            }
        
        if task.goal:
            result['goal'] = {
                'type': task.goal.type.value if task.goal.type else None,
                'deadline': str(task.goal.deadline) if task.goal.deadline else None
            }
        
        # Add enhanced statistics with optimized distance calculations
        result['stats'] = {
            'totalDistance': distance_data['center_distance_km'],
            'totalOptimizedDistance': distance_data['optimized_distance_km'],
            'optimizationSavings': distance_data['savings_km'],
            'optimizationSavingsPercent': distance_data['savings_percent'],
            'turnpointCount': len(task.turnpoints),
            'taskType': task.task_type.value,
            'cylinderCount': sum(1 for tp in task.turnpoints if tp.radius > 0)
        }
        
        return result
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two coordinates in km using Haversine formula."""
        import math
        
        # Convert to radians
        lat1_r = math.radians(lat1)
        lon1_r = math.radians(lon1)
        lat2_r = math.radians(lat2)
        lon2_r = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_r - lat1_r
        dlon = lon2_r - lon1_r
        a = math.sin(dlat/2)**2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth radius in km
        R = 6371
        return R * c
    
    def run(self, host: str = '127.0.0.1', port: int = 5000, debug: Optional[bool] = None):
        """Run the web application."""
        if debug is not None:
            self.app.config['DEBUG'] = debug
        self.app.run(host=host, port=port, debug=self.app.config['DEBUG'])


def create_app(debug: bool = False, task_directory: Optional[str] = None) -> Flask:
    """Create and configure the Flask app."""
    web_app = XCTrackWebApp(debug=debug, task_directory=task_directory)
    return web_app.app
