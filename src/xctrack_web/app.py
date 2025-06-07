"""Flask web application for XCTrack task visualization."""

import base64
import json
from datetime import datetime
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
        
        # Distance calculation cache to improve performance
        self._distance_cache = {}
        
        # Set default task directory
        if tasks_dir:
            self.task_directory = Path(tasks_dir)
        else:
            # Default to tests directory in the parent project
            self.task_directory = Path(__file__).parent.parent.parent / 'tests'
        
        # Directory for saved uploaded tasks
        self.saved_tasks_dir = Path(__file__).parent / 'static' / 'saved_tasks'
        self.saved_tasks_dir.mkdir(parents=True, exist_ok=True)
        
        # Directory for saved task metadata
        self.saved_tasks_metadata_dir = Path(__file__).parent / 'static' / 'saved_tasks_metadata'
        self.saved_tasks_metadata_dir.mkdir(parents=True, exist_ok=True)
        
        # Directory for cached distance calculations
        self.distance_cache_dir = Path(__file__).parent / 'static' / 'distance_cache'
        self.distance_cache_dir.mkdir(parents=True, exist_ok=True)
        
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
                task_dict = self._task_to_dict(task)
                
                # Generate a unique filename based on timestamp and original filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                original_filename = file.filename
                if original_filename.endswith('.xctsk'):
                    base_name = original_filename[:-6]  # Remove .xctsk extension
                else:
                    base_name = original_filename
                
                # Clean the filename
                clean_name = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
                if not clean_name:
                    clean_name = "uploaded_task"
                
                saved_filename = f"{timestamp}_{clean_name}.xctsk"
                saved_file_path = self.saved_tasks_dir / saved_filename
                
                # Save the original task file
                with open(saved_file_path, 'wb') as f:
                    f.write(task_data)
                
                # Save task metadata for quick access
                metadata = {
                    'filename': saved_filename,
                    'original_filename': original_filename,
                    'upload_time': timestamp,
                    'task_name': task_dict.get('turnpoints', [{}])[0].get('name', clean_name) if task_dict.get('turnpoints') else clean_name,
                    'distance': task_dict['stats']['totalDistance'],
                    'optimized_distance': task_dict['stats']['totalOptimizedDistance'],
                    'turnpoint_count': task_dict['stats']['turnpointCount'],
                    'task_type': task_dict['taskType'],
                    'cache_key': self._get_task_cache_key(task)  # Store cache key for faster lookups
                }
                
                metadata_file = self.saved_tasks_metadata_dir / f"{timestamp}_{clean_name}.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2)
                
                # Add the saved file info to the response
                task_dict['saved_as'] = saved_filename
                task_dict['saved_timestamp'] = timestamp
                
                return jsonify(task_dict)
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/tasks')
        def api_list_tasks():
            """API endpoint to list available tasks."""
            try:
                tasks = []
                
                # Load sample tasks from tests directory
                if self.task_directory.exists():
                    for task_file in self.task_directory.glob('*.xctsk'):
                        try:
                            with open(task_file, 'r') as f:
                                task_data = f.read()
                            task = parse_task(task_data)
                            
                            # Check if we have cached distance data first
                            cache_key = self._get_task_cache_key(task)
                            distance_data = self._load_cached_distances(cache_key)
                            
                            if distance_data is None:
                                # Calculate if not cached (with faster settings for listing)
                                distance_data = calculate_task_distances(task, angle_step=15)  # Faster for listings
                                self._save_cached_distances(cache_key, distance_data)
                            
                            tasks.append({
                                'code': task_file.stem.replace('task_', ''),
                                'name': f"Task {task_file.stem}",
                                'distance': distance_data['center_distance_km'],
                                'optimizedDistance': distance_data['optimized_distance_km'],
                                'savings': distance_data['savings_km'],
                                'savingsPercent': distance_data['savings_percent'],
                                'turnpoints': len(task.turnpoints),
                                'cylinders': sum(1 for tp in task.turnpoints if tp.radius > 0),
                                'type': task.task_type.value,
                                'source': 'sample'
                            })
                        except Exception as e:
                            print(f"Error processing task {task_file}: {e}")
                            continue
                
                # Load saved tasks from metadata
                saved_tasks = self._get_saved_tasks()
                tasks.extend(saved_tasks)
                
                return jsonify({'tasks': tasks})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/saved-tasks')
        def api_list_saved_tasks():
            """API endpoint to list only saved tasks."""
            try:
                saved_tasks = self._get_saved_tasks()
                return jsonify({'tasks': saved_tasks})
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        @self.app.route('/api/task/saved/<filename>')
        def api_get_saved_task(filename: str):
            """API endpoint to get saved task data."""
            try:
                task_file = self.saved_tasks_dir / filename
                
                if task_file.exists() and task_file.suffix == '.xctsk':
                    with open(task_file, 'r') as f:
                        task_data = f.read()
                    task = parse_task(task_data)
                    return jsonify(self._task_to_dict(task))
                else:
                    return jsonify({'error': 'Saved task not found'}), 404
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/task/<task_code>/optimized-route')
        def api_get_optimized_route(task_code: str):
            """API endpoint to get optimized route coordinates for a task."""
            try:
                # Load task
                task_file = self._find_task_file(task_code)
                
                if task_file and task_file.exists():
                    with open(task_file, 'r') as f:
                        task_data = f.read()
                    task = parse_task(task_data)
                    
                    # Convert task turnpoints to distance calculation format
                    from xctrack.distance import TaskTurnpoint, optimized_route_coordinates
                    from geopy.distance import geodesic
                    turnpoints = []
                    for tp in task.turnpoints:
                        task_tp = TaskTurnpoint(tp.waypoint.lat, tp.waypoint.lon, tp.radius)
                        turnpoints.append(task_tp)
                    
                    # Calculate optimized route coordinates
                    route_coords = optimized_route_coordinates(turnpoints, angle_step=10)
                    
                    # Convert to the format expected by the frontend
                    route_data = [{'lat': lat, 'lon': lon} for lat, lon in route_coords]
                    
                    return jsonify({
                        'route': route_data,
                        'distance_km': sum(geodesic(route_coords[i], route_coords[i+1]).meters 
                                         for i in range(len(route_coords)-1)) / 1000.0
                    })
                else:
                    return jsonify({'error': 'Task not found'}), 404
            except Exception as e:
                return jsonify({'error': str(e)}), 500

    def _get_saved_tasks(self):
        """Get list of saved tasks from metadata files."""
        saved_tasks = []
        
        if self.saved_tasks_metadata_dir.exists():
            for metadata_file in self.saved_tasks_metadata_dir.glob('*.json'):
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    saved_tasks.append({
                        'code': metadata['filename'],
                        'name': metadata.get('task_name', metadata['original_filename']),
                        'distance': metadata['distance'],
                        'optimizedDistance': metadata['optimized_distance'],
                        'turnpoints': metadata['turnpoint_count'],
                        'type': metadata['task_type'],
                        'source': 'uploaded',
                        'upload_time': metadata['upload_time'],
                        'original_filename': metadata['original_filename']
                    })
                except Exception:
                    continue
        
        # Sort by upload time (newest first)
        saved_tasks.sort(key=lambda x: x['upload_time'], reverse=True)
        return saved_tasks

    def _find_task_file(self, task_code: str) -> Optional[Path]:
        """Find a task file by code."""
        # First try saved tasks (uploaded files)
        if task_code.endswith('.xctsk'):
            # Direct filename lookup for saved tasks
            saved_task_file = self.saved_tasks_dir / task_code
            if saved_task_file.exists():
                return saved_task_file
        else:
            # Try with .xctsk extension for saved tasks
            saved_task_file = self.saved_tasks_dir / f'{task_code}.xctsk'
            if saved_task_file.exists():
                return saved_task_file
        
        # Try different naming patterns for sample tasks
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
    
    def _get_task_cache_key(self, task: Task) -> str:
        """Generate a cache key for a task based on its content."""
        import hashlib
        
        # Create a unique identifier based on task turnpoints and properties
        cache_data = {
            'task_type': task.task_type.value,
            'version': task.version,
            'turnpoints': []
        }
        
        for tp in task.turnpoints:
            cache_data['turnpoints'].append({
                'lat': round(tp.waypoint.lat, 6),  # Round to avoid floating point precision issues
                'lon': round(tp.waypoint.lon, 6),
                'radius': tp.radius,
                'type': tp.type.value if tp.type else None
            })
        
        # Create hash from the serialized data
        cache_str = str(sorted(cache_data.items()))
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def _load_cached_distances(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Load cached distance calculations from file."""
        cache_file = self.distance_cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception:
                # If cache file is corrupted, ignore it
                pass
        return None
    
    def _save_cached_distances(self, cache_key: str, distance_data: Dict[str, Any]) -> None:
        """Save distance calculations to cache file."""
        cache_file = self.distance_cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump(distance_data, f, indent=2)
        except Exception:
            # If we can't save cache, continue without it
            pass
    
    def _task_to_dict(self, task: Task) -> Dict[str, Any]:
        """Convert a task to a dictionary for JSON serialization."""
        # Check persistent cache first
        cache_key = self._get_task_cache_key(task)
        distance_data = self._load_cached_distances(cache_key)
        
        if distance_data is None:
            # Check memory cache
            if cache_key in self._distance_cache:
                distance_data = self._distance_cache[cache_key]
            else:
                # Calculate distances with faster settings for web interface
                print(f"Calculating distances for task with {len(task.turnpoints)} turnpoints...")
                distance_data = calculate_task_distances(task, angle_step=10)  # Use 10° for faster web response
                
                # Cache in both memory and persistent storage
                self._distance_cache[cache_key] = distance_data
                self._save_cached_distances(cache_key, distance_data)
                print(f"Distance calculation complete: {distance_data['center_distance_km']:.1f}km center, {distance_data['optimized_distance_km']:.1f}km optimized")
        
        result = {
            'taskType': task.task_type.value,
            'version': task.version,
            'earthModel': task.earth_model.value if task.earth_model else None,
            'turnpoints': [],
            'stats': {}
        }
        
        # Add turnpoint data with both basic and optimized distances
        for i, tp in enumerate(task.turnpoints):
            # Get distance data for this turnpoint, handling missing data gracefully
            tp_distance_data = {}
            if i < len(distance_data.get('turnpoints', [])):
                tp_distance_data = distance_data['turnpoints'][i]
            
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
                'cumulative_center_km': tp_distance_data.get('cumulative_center_km', 0),
                'cumulative_optimized_km': tp_distance_data.get('cumulative_optimized_km', 0),
                # Keep old field names for backwards compatibility
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
