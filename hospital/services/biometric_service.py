"""
World-Class Biometric Authentication Service
Implements Face Recognition with Liveness Detection and Anti-Spoofing
Based on DeepFace, FaceNet, and industry best practices
"""
import base64
import hashlib
import io
import json
import time
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction
from typing import Optional, Dict, Tuple, List, Any
import logging

logger = logging.getLogger(__name__)

# Optional imports for biometric features
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    logger.warning("numpy not available - biometric features will be disabled")
    NUMPY_AVAILABLE = False
    np = None


def convert_numpy_types(obj: Any) -> Any:
    """
    Recursively convert NumPy types to Python native types for JSON serialization
    
    Args:
        obj: Object to convert
        
    Returns:
        Converted object with Python native types
    """
    if not NUMPY_AVAILABLE or np is None:
        # If numpy not available, just return the object as-is
        return obj
    
    if isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_types(item) for item in obj)
    else:
        return obj


class BiometricService:
    """
    Core biometric authentication service
    """
    
    def __init__(self):
        self.face_recognition_available = False
        self.deepface_available = False
        self.cv2_available = False
        
        # Try to import face recognition libraries
        try:
            import deepface
            from deepface import DeepFace
            self.DeepFace = DeepFace
            self.deepface_available = True
            logger.info("DeepFace library loaded successfully")
        except ImportError as e:
            logger.warning(f"DeepFace not available. Install with: pip install deepface - {e}")
        except Exception as e:
            logger.error(f"Error loading DeepFace: {e}")
        
        try:
            import cv2
            self.cv2 = cv2
            self.cv2_available = True
            logger.info("OpenCV loaded successfully")
        except ImportError as e:
            logger.warning(f"OpenCV not available. Install with: pip install opencv-python - {e}")
        except Exception as e:
            logger.error(f"Error loading OpenCV: {e}")
        
        try:
            import face_recognition
            self.face_recognition = face_recognition
            self.face_recognition_available = True
            logger.info("face_recognition library loaded successfully")
        except ImportError as e:
            logger.warning(f"face_recognition not available. Install with: pip install face_recognition - {e}")
        except Exception as e:
            logger.error(f"Error loading face_recognition: {e}")
    
    def is_available(self) -> bool:
        """Check if biometric services are available"""
        return self.deepface_available or self.face_recognition_available
    
    def encode_face(self, image_data: bytes, model: str = 'Facenet512') -> Tuple[Optional[np.ndarray], Dict]:
        """
        Generate face encoding/embedding from image
        
        Args:
            image_data: Raw image bytes
            model: Face recognition model to use
        
        Returns:
            Tuple of (encoding_array, metadata)
        """
        start_time = time.time()
        metadata = {
            'model': model,
            'timestamp': timezone.now().isoformat(),
            'quality_checks': {}
        }
        
        try:
            # Convert bytes to numpy array
            if self.cv2_available:
                nparr = np.frombuffer(image_data, np.uint8)
                img = self.cv2.imdecode(nparr, self.cv2.IMREAD_COLOR)
                
                # Quality checks
                metadata['quality_checks']['resolution'] = f"{img.shape[1]}x{img.shape[0]}"
                metadata['quality_checks']['color_space'] = 'BGR'
                
                # Check image brightness
                gray = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2GRAY)
                brightness = np.mean(gray)
                metadata['quality_checks']['brightness'] = float(brightness)
                
                # Check image sharpness (using Laplacian variance)
                laplacian_var = self.cv2.Laplacian(gray, self.cv2.CV_64F).var()
                metadata['quality_checks']['sharpness'] = float(laplacian_var)
            
            # Use DeepFace if available (preferred)
            if self.deepface_available:
                # Save temp image for DeepFace
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                    tmp_file.write(image_data)
                    tmp_path = tmp_file.name
                
                try:
                    # Extract face embedding using DeepFace
                    # Use opencv detector - fast, reliable, no extra downloads needed
                    embedding_objs = self.DeepFace.represent(
                        img_path=tmp_path,
                        model_name=model,
                        enforce_detection=True,
                        detector_backend='opencv',  # Fast and reliable
                        align=True
                    )
                    metadata['detector_backend'] = 'opencv'
                    logger.debug(f"Successfully detected face using opencv detector")
                    
                    if embedding_objs and len(embedding_objs) > 0:
                        embedding = embedding_objs[0]['embedding']
                        metadata['face_detected'] = True
                        metadata['num_faces'] = len(embedding_objs)
                        
                        # Additional face detection metadata
                        if 'facial_area' in embedding_objs[0]:
                            facial_area = embedding_objs[0]['facial_area']
                            metadata['facial_area'] = facial_area
                            
                            # Calculate face size as quality indicator
                            face_width = facial_area['w']
                            face_height = facial_area['h']
                            metadata['quality_checks']['face_size'] = f"{face_width}x{face_height}"
                        
                        processing_time = (time.time() - start_time) * 1000
                        metadata['processing_time_ms'] = int(processing_time)
                        
                        return np.array(embedding), metadata
                    else:
                        metadata['error'] = 'No face detected'
                        return None, metadata
                        
                except Exception as e:
                    logger.error(f"DeepFace encoding error: {str(e)}")
                    metadata['error'] = str(e)
                    return None, metadata
                finally:
                    # Clean up temp file
                    import os
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
            
            # Fallback to face_recognition library
            elif self.face_recognition_available:
                # Load image
                import PIL.Image
                image = PIL.Image.open(io.BytesIO(image_data))
                image_array = np.array(image)
                
                # Find face locations
                face_locations = self.face_recognition.face_locations(image_array)
                metadata['num_faces'] = len(face_locations)
                
                if len(face_locations) == 0:
                    metadata['error'] = 'No face detected'
                    return None, metadata
                
                if len(face_locations) > 1:
                    metadata['warning'] = 'Multiple faces detected, using first face'
                
                # Generate encoding
                face_encodings = self.face_recognition.face_encodings(
                    image_array,
                    face_locations
                )
                
                if len(face_encodings) > 0:
                    metadata['face_detected'] = True
                    metadata['face_location'] = face_locations[0]
                    processing_time = (time.time() - start_time) * 1000
                    metadata['processing_time_ms'] = int(processing_time)
                    
                    return face_encodings[0], metadata
                else:
                    metadata['error'] = 'Failed to encode face'
                    return None, metadata
            
            else:
                metadata['error'] = 'No face recognition library available'
                return None, metadata
                
        except Exception as e:
            logger.exception("Error encoding face")
            metadata['error'] = str(e)
            return None, metadata
    
    def compare_faces(
        self,
        encoding1: np.ndarray,
        encoding2: np.ndarray,
        threshold: float = 0.7
    ) -> Tuple[bool, float]:
        """
        Compare two face encodings using multiple distance metrics
        
        Args:
            encoding1: First face encoding
            encoding2: Second face encoding
            threshold: Matching threshold (lower = more strict)
        
        Returns:
            Tuple of (is_match, confidence_score)
        """
        try:
            # Normalize encodings
            encoding1_norm = encoding1 / np.linalg.norm(encoding1)
            encoding2_norm = encoding2 / np.linalg.norm(encoding2)
            
            # Method 1: Cosine Similarity (better for FaceNet embeddings)
            cosine_sim = np.dot(encoding1_norm, encoding2_norm)
            cosine_distance = 1 - cosine_sim
            
            # Method 2: Euclidean distance (normalized)
            euclidean_distance = np.linalg.norm(encoding1_norm - encoding2_norm)
            
            # Convert to confidence score (0-100)
            # Cosine similarity: 1.0 = identical, 0.0 = orthogonal, -1.0 = opposite
            # Convert to percentage: (similarity + 1) / 2 * 100
            confidence_cosine = float((cosine_sim + 1) / 2 * 100)
            
            # Euclidean (normalized): 0 = identical, ~2.0 = very different
            # Convert: confidence = 100 * (1 - distance/2)
            confidence_euclidean = float(100 * max(0, (1 - euclidean_distance / 2)))
            
            # Use weighted average (cosine is more reliable for embeddings)
            confidence = 0.7 * confidence_cosine + 0.3 * confidence_euclidean
            confidence = max(0, min(100, confidence))
            
            # Determine if match (using cosine distance)
            is_match = cosine_distance < threshold
            
            logger.debug(f"Face comparison: cosine_dist={cosine_distance:.4f}, euclidean={euclidean_distance:.4f}, confidence={confidence:.2f}, match={is_match}")
            
            return is_match, confidence
            
        except Exception as e:
            logger.exception("Error comparing faces")
            return False, 0.0
    
    def calculate_quality_score(self, image_data: bytes, metadata: Dict) -> Decimal:
        """
        Calculate overall quality score for biometric sample
        
        Args:
            image_data: Raw image bytes
            metadata: Metadata from encoding process
        
        Returns:
            Quality score (0-100)
        """
        quality_score = Decimal('100.00')
        quality_checks = metadata.get('quality_checks', {})
        
        # Check brightness (optimal: 100-150)
        brightness = quality_checks.get('brightness', 0)
        if brightness < 80:
            quality_score -= Decimal('20.00')  # Too dark
        elif brightness > 180:
            quality_score -= Decimal('15.00')  # Too bright
        elif brightness < 100 or brightness > 150:
            quality_score -= Decimal('10.00')  # Slightly off
        
        # Check sharpness (optimal: > 100)
        sharpness = quality_checks.get('sharpness', 0)
        if sharpness < 50:
            quality_score -= Decimal('30.00')  # Very blurry
        elif sharpness < 100:
            quality_score -= Decimal('15.00')  # Slightly blurry
        
        # Check face size
        face_size = quality_checks.get('face_size', '')
        if face_size:
            try:
                width, height = map(int, face_size.split('x'))
                if width < 100 or height < 100:
                    quality_score -= Decimal('20.00')  # Face too small
            except:
                pass
        
        # Check for multiple faces
        num_faces = metadata.get('num_faces', 1)
        if num_faces > 1:
            quality_score -= Decimal('15.00')  # Multiple faces detected
        elif num_faces == 0:
            quality_score = Decimal('0.00')  # No face detected
        
        # Ensure score is between 0 and 100
        quality_score = max(Decimal('0.00'), min(Decimal('100.00'), quality_score))
        
        return quality_score
    
    def detect_liveness(self, image_data: bytes, lenient_mode: bool = False) -> Tuple[bool, Decimal, Dict]:
        """
        Perform liveness detection to prevent spoofing attacks
        
        Args:
            image_data: Raw image bytes
            lenient_mode: If True, use more relaxed thresholds (for enrollment)
        
        Returns:
            Tuple of (is_live, liveness_score, metadata)
        """
        metadata = {}
        liveness_score = Decimal('60.00') if lenient_mode else Decimal('50.00')  # Higher starting score in lenient mode
        
        try:
            if not self.cv2_available:
                metadata['warning'] = 'OpenCV not available, liveness detection limited'
                return True, liveness_score, metadata
            
            # Convert to image
            nparr = np.frombuffer(image_data, np.uint8)
            img = self.cv2.imdecode(nparr, self.cv2.IMREAD_COLOR)
            gray = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2GRAY)
            
            # Check 1: Texture analysis (photos have less texture variation)
            laplacian_var = self.cv2.Laplacian(gray, self.cv2.CV_64F).var()
            metadata['texture_variance'] = float(laplacian_var)
            
            if laplacian_var > 100:
                liveness_score += Decimal('20.00')
            elif laplacian_var < 30:
                liveness_score -= Decimal('15.00')  # Reduced penalty
            
            # Check 2: Color analysis (printed photos have different color distribution)
            hsv = self.cv2.cvtColor(img, self.cv2.COLOR_BGR2HSV)
            color_std = np.std(hsv[:, :, 1])  # Saturation channel
            metadata['color_std'] = float(color_std)
            
            if color_std > 30:
                liveness_score += Decimal('15.00')
            elif color_std < 15:
                liveness_score -= Decimal('10.00')  # Reduced penalty
            
            # Check 3: Detect screen patterns (Moiré effect)
            # Use FFT to detect regular patterns typical of screens
            f_transform = np.fft.fft2(gray)
            f_shift = np.fft.fftshift(f_transform)
            magnitude = 20 * np.log(np.abs(f_shift) + 1)
            
            # High frequency peaks indicate screen patterns
            high_freq_energy = np.sum(magnitude[magnitude > np.mean(magnitude) + 2 * np.std(magnitude)])
            metadata['high_freq_energy'] = float(high_freq_energy)
            
            if high_freq_energy > 1000000:
                liveness_score -= Decimal('15.00')  # Reduced penalty for screen detection
                metadata['screen_pattern_detected'] = True
            
            # Ensure score is between 0 and 100
            liveness_score = max(Decimal('0.00'), min(Decimal('100.00'), liveness_score))
            
            # Threshold for liveness
            threshold = Decimal('30.00') if lenient_mode else Decimal('40.00')
            is_live = liveness_score >= threshold
            
            metadata['liveness_checks'] = {
                'texture_check': bool(laplacian_var > 100),
                'color_check': bool(color_std > 30),
                'screen_check': bool(high_freq_energy < 1000000),
            }
            
            return is_live, liveness_score, metadata
            
        except Exception as e:
            logger.exception("Error in liveness detection")
            metadata['error'] = str(e)
            # Default to accepting if liveness check fails (graceful degradation)
            return True, Decimal('50.00'), metadata
    
    def generate_template_hash(self, encoding: np.ndarray) -> str:
        """
        Generate SHA-256 hash of face encoding for indexing
        
        Args:
            encoding: Face encoding array
        
        Returns:
            Hash string
        """
        # Convert encoding to bytes
        encoding_bytes = encoding.tobytes()
        
        # Generate hash
        hash_obj = hashlib.sha256(encoding_bytes)
        return hash_obj.hexdigest()
    
    def serialize_encoding(self, encoding: np.ndarray) -> bytes:
        """
        Serialize face encoding for storage
        
        Args:
            encoding: Face encoding array
        
        Returns:
            Serialized bytes
        """
        return encoding.tobytes()
    
    def deserialize_encoding(self, data: bytes, dtype=np.float64) -> np.ndarray:
        """
        Deserialize stored face encoding
        
        Args:
            data: Serialized encoding bytes
            dtype: Data type of encoding
        
        Returns:
            Face encoding array
        """
        return np.frombuffer(data, dtype=dtype)


class BiometricAuthenticationService:
    """
    High-level service for biometric authentication operations
    """
    
    def __init__(self):
        self.biometric_service = BiometricService()
    
    @transaction.atomic
    def enroll_staff_biometric(
        self,
        staff,
        biometric_type,
        image_data: bytes,
        operator: User,
        device=None,
        location: str = ''
    ) -> Tuple[bool, Optional[object], str]:
        """
        Enroll staff member with biometric data
        
        Args:
            staff: Staff object
            biometric_type: BiometricType object
            image_data: Raw image bytes
            operator: User performing enrollment
            device: BiometricDevice object (optional)
            location: Location name
        
        Returns:
            Tuple of (success, staff_biometric_object, message)
        """
        from hospital.models_biometric import StaffBiometric
        
        try:
            # Check if biometric service is available
            if not self.biometric_service.is_available():
                return False, None, "Biometric service not available. Please install required libraries."
            
            # Generate face encoding
            encoding, metadata = self.biometric_service.encode_face(image_data)
            
            if encoding is None:
                error_msg = metadata.get('error', 'Failed to process biometric data')
                return False, None, f"Enrollment failed: {error_msg}"
            
            # Check for multiple faces
            if metadata.get('num_faces', 0) > 1:
                return False, None, "Multiple faces detected. Please ensure only one person is in the frame."
            
            # Perform liveness detection (lenient mode for enrollment)
            is_live, liveness_score, liveness_metadata = self.biometric_service.detect_liveness(image_data, lenient_mode=True)
            
            if not is_live:
                return False, None, f"Liveness check failed. Please use a live camera feed. (Score: {liveness_score})"
            
            # Calculate quality score
            quality_score = self.biometric_service.calculate_quality_score(image_data, metadata)
            
            # Check minimum quality (lowered to 45 for better usability)
            if quality_score < Decimal('45.00'):
                return False, None, f"Image quality too low ({quality_score}/100). Please improve lighting and focus."
            
            # Generate template hash and data
            template_hash = self.biometric_service.generate_template_hash(encoding)
            template_data = self.biometric_service.serialize_encoding(encoding)
            
            # Prepare metadata
            full_metadata = {
                **metadata,
                'liveness_score': str(liveness_score),
                'liveness_metadata': liveness_metadata,
                'enrollment_timestamp': timezone.now().isoformat(),
                'operator_id': operator.id,
                'operator_username': operator.username,
            }
            
            if device:
                full_metadata['device_id'] = str(device.id)
                full_metadata['device_name'] = device.device_name
            
            # Convert NumPy types to Python types for JSON serialization
            full_metadata = convert_numpy_types(full_metadata)
            
            # Create StaffBiometric record
            staff_biometric = StaffBiometric.objects.create(
                staff=staff,
                biometric_type=biometric_type,
                template_hash=template_hash,
                template_data=template_data,
                template_metadata=full_metadata,
                enrolled_by=operator,
                enrollment_device=device.device_name if device else '',
                enrollment_location=location,
                quality_score=quality_score,
                sample_count=1,
                is_active=True,
                is_primary=True,
            )
            
            logger.info(f"Successfully enrolled biometric for staff {staff.user.username}")
            
            return True, staff_biometric, f"Biometric enrollment successful! Quality: {quality_score}/100"
            
        except Exception as e:
            logger.exception("Error during biometric enrollment")
            return False, None, f"Enrollment error: {str(e)}"
    
    @transaction.atomic
    def authenticate_staff(
        self,
        image_data: bytes,
        biometric_type,
        device=None,
        location: str = '',
        ip_address: str = '',
        create_attendance: bool = True,
        create_login: bool = True
    ) -> Tuple[bool, Optional[object], str, Dict]:
        """
        Authenticate staff using biometric data
        
        Args:
            image_data: Raw image bytes
            biometric_type: BiometricType object
            device: BiometricDevice object (optional)
            location: Location name
            ip_address: Client IP address
            create_attendance: Whether to create attendance record
            create_login: Whether to create login history record
        
        Returns:
            Tuple of (success, staff_object, message, metadata)
        """
        from hospital.models_biometric import (
            StaffBiometric,
            BiometricAuthenticationLog,
            BiometricSecurityAlert
        )
        from hospital.models_advanced import Attendance
        from hospital.models_login_tracking import LoginHistory
        
        start_time = time.time()
        auth_metadata = {}
        
        try:
            # Check if biometric service is available
            if not self.biometric_service.is_available():
                return False, None, "Biometric service not available", {}
            
            # Generate face encoding from input
            logger.info(f"Starting face encoding for authentication...")
            encoding, metadata = self.biometric_service.encode_face(image_data)
            
            if encoding is None:
                error_msg = metadata.get('error', 'Failed to process biometric data')
                logger.error(f"Face encoding failed: {error_msg}")
                logger.debug(f"Metadata: {metadata}")
                self._log_failed_auth(
                    None,
                    biometric_type,
                    'failed_quality',
                    error_msg,
                    device,
                    location,
                    ip_address,
                    metadata
                )
                return False, None, f"Authentication failed: {error_msg}", metadata
            
            logger.info(f"Face encoded successfully. Encoding shape: {encoding.shape}, detector: {metadata.get('detector_backend', 'unknown')}")
            
            # Perform liveness detection
            is_live, liveness_score, liveness_metadata = self.biometric_service.detect_liveness(image_data)
            
            if not is_live:
                self._log_failed_auth(
                    None,
                    biometric_type,
                    'failed_liveness',
                    f"Liveness check failed (score: {liveness_score})",
                    device,
                    location,
                    ip_address,
                    {**metadata, **liveness_metadata}
                )
                return False, None, "Liveness check failed", metadata
            
            # Calculate quality score
            quality_score = self.biometric_service.calculate_quality_score(image_data, metadata)
            
            if quality_score < Decimal('40.00'):
                self._log_failed_auth(
                    None,
                    biometric_type,
                    'failed_quality',
                    f"Quality too low: {quality_score}/100",
                    device,
                    location,
                    ip_address,
                    metadata
                )
                return False, None, f"Image quality too low ({quality_score}/100)", metadata
            
            # Search for matching biometric templates
            active_biometrics = StaffBiometric.objects.filter(
                biometric_type=biometric_type,
                is_active=True,
                is_deleted=False
            ).select_related('staff', 'staff__user')
            
            logger.info(f"Searching through {active_biometrics.count()} enrolled biometric(s)...")
            
            best_match = None
            best_confidence = 0.0
            
            for staff_biometric in active_biometrics:
                # Check if locked
                if staff_biometric.is_locked:
                    continue
                
                # Check if expired
                if staff_biometric.is_expired:
                    continue
                
                # Deserialize stored encoding
                stored_encoding = self.biometric_service.deserialize_encoding(
                    staff_biometric.template_data
                )
                
                # Compare encodings (using cosine distance threshold)
                is_match, confidence = self.biometric_service.compare_faces(
                    encoding,
                    stored_encoding,
                    threshold=0.4  # Cosine distance threshold (0.4 = ~80% similarity)
                )
                
                logger.info(f"Comparing with {staff_biometric.staff.user.get_full_name()}: match={is_match}, confidence={confidence:.2f}%")
                
                if is_match and confidence > best_confidence:
                    best_match = staff_biometric
                    best_confidence = confidence
                    logger.info(f"New best match: {staff_biometric.staff.user.get_full_name()} with {confidence:.2f}% confidence")
            
            processing_time = int((time.time() - start_time) * 1000)
            
            # Check if match found
            logger.info(f"Authentication result: best_match={best_match is not None}, best_confidence={best_confidence:.2f}, min_required={biometric_type.min_confidence_score}")
            
            if best_match and best_confidence >= float(biometric_type.min_confidence_score):
                # Successful authentication
                staff = best_match.staff
                
                # Update biometric record
                best_match.record_successful_verification()
                
                # Create authentication log
                auth_log = BiometricAuthenticationLog.objects.create(
                    staff=staff,
                    biometric=best_match,
                    biometric_type=biometric_type,
                    status='success',
                    confidence_score=Decimal(str(best_confidence)),
                    quality_score=quality_score,
                    liveness_score=liveness_score,
                    device_id=device.device_id if device else '',
                    device_name=device.device_name if device else '',
                    device_info=metadata,
                    location_name=location,
                    ip_address=ip_address or None,
                    processing_time_ms=processing_time,
                )
                
                # Create attendance record if requested
                if create_attendance:
                    today = timezone.now().date()
                    attendance, created = Attendance.objects.get_or_create(
                        staff=staff,
                        date=today,
                        defaults={
                            'check_in': timezone.now(),
                            'status': 'present',
                            'notes': f'Auto check-in via {biometric_type.display_name}'
                        }
                    )
                    
                    if created:
                        auth_log.created_attendance = True
                        auth_log.attendance_record = attendance
                        auth_log.save(update_fields=['created_attendance', 'attendance_record'])
                
                # Create login history if requested
                if create_login:
                    login_history = LoginHistory.objects.create(
                        user=staff.user,
                        staff=staff,
                        login_time=timezone.now(),
                        ip_address=ip_address or '0.0.0.0',
                        device_name=device.device_name if device else 'Biometric Device',
                        device_type='biometric',
                        status='success',
                        notes=f'Biometric login via {biometric_type.display_name}'
                    )
                    
                    auth_log.created_login_record = True
                    auth_log.login_record = login_history
                    auth_log.save(update_fields=['created_login_record', 'login_record'])
                
                # Update device statistics
                if device:
                    device.total_authentications += 1
                    device.successful_authentications += 1
                    device.last_heartbeat = timezone.now()
                    device.save(update_fields=[
                        'total_authentications',
                        'successful_authentications',
                        'last_heartbeat'
                    ])
                
                logger.info(f"Successful biometric authentication for {staff.user.username} (confidence: {best_confidence})")
                
                auth_metadata = {
                    'confidence': best_confidence,
                    'quality_score': str(quality_score),
                    'liveness_score': str(liveness_score),
                    'processing_time_ms': processing_time,
                }
                
                # Convert NumPy types for JSON serialization
                auth_metadata = convert_numpy_types(auth_metadata)
                
                return True, staff, f"Welcome, {staff.user.get_full_name()}!", auth_metadata
            
            else:
                # No match found
                fail_reason = f"No matching biometric found (best confidence: {best_confidence:.2f}%, required: {biometric_type.min_confidence_score}%)"
                logger.warning(f"Authentication failed: {fail_reason}")
                
                self._log_failed_auth(
                    None,
                    biometric_type,
                    'failed_match',
                    fail_reason,
                    device,
                    location,
                    ip_address,
                    {**metadata, 'best_confidence': best_confidence}
                )
                
                # Update device statistics
                if device:
                    device.total_authentications += 1
                    device.failed_authentications += 1
                    device.save(update_fields=[
                        'total_authentications',
                        'failed_authentications'
                    ])
                
                # Convert NumPy types for JSON serialization
                metadata = convert_numpy_types(metadata)
                return False, None, "Authentication failed: No matching biometric found", metadata
                
        except Exception as e:
            logger.exception("Error during biometric authentication")
            return False, None, f"Authentication error: {str(e)}", {}
    
    def _log_failed_auth(
        self,
        staff,
        biometric_type,
        status: str,
        reason: str,
        device,
        location: str,
        ip_address: str,
        metadata: Dict
    ):
        """Log failed authentication attempt"""
        from hospital.models_biometric import BiometricAuthenticationLog
        
        try:
            BiometricAuthenticationLog.objects.create(
                staff=staff,
                biometric=None,
                biometric_type=biometric_type,
                status=status,
                device_id=device.device_id if device else '',
                device_name=device.device_name if device else '',
                device_info=metadata,
                location_name=location,
                ip_address=ip_address or None,
                failure_reason=reason,
            )
        except Exception as e:
            logger.error(f"Failed to log authentication failure: {e}")


# Global service instance
try:
    biometric_service = BiometricService()
    biometric_auth_service = BiometricAuthenticationService()
    logger.info("Biometric services initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize biometric services: {e}")
    # Create a dummy service that reports as unavailable
    biometric_service = BiometricService()
    biometric_auth_service = BiometricAuthenticationService()

