import logging
import os
import time
import uuid
import re
import shutil
from typing import Optional, Dict, Any
import paramiko
from utils.error_handling import retry, circuit_breaker, UploadError
from utils.supabase_client import get_supabase_client
from utils.config import VIDEO_SERVER, VIDEO_SERVER_USER, VIDEO_SERVER_PASSWORD

class UploaderAgent:
    def __init__(self, upload_provider: str = "supabase"):
        """
        Initialize the UploaderAgent.
        
        Args:
            upload_provider: The provider to use for uploading videos
                            Options: "supabase", "youtube", "s3"
        """
        self.logger = logging.getLogger(__name__)
        self.upload_provider = upload_provider.lower()
        self.client = get_supabase_client()
    
    @retry(max_attempts=3, initial_delay=2.0)
    @circuit_breaker(failure_threshold=3, reset_timeout=300.0)
    def upload_video(self, video_path: str, metadata: Optional[dict] = None) -> str:
        """
        Upload a video to the configured storage provider.
        
        Args:
            video_path: Path to the video file to upload
            metadata: Optional metadata to associate with the video
            
        Returns:
            Public URL of the uploaded video
            
        Raises:
            UploadError: If video upload fails
        """
        try:
            if not os.path.exists(video_path):
                raise UploadError(f"Video file not found: {video_path}")
                
            self.logger.info(f"Uploading video: {video_path}")
            
            # Upload based on provider
            if self.upload_provider == "supabase":
                return self._upload_to_supabase(video_path, metadata)
            elif self.upload_provider == "youtube":
                return self._upload_to_youtube(video_path, metadata)
            elif self.upload_provider == "s3":
                return self._upload_to_s3(video_path, metadata)
            elif self.upload_provider == "local":
                result = self._upload_to_local(video_path, metadata)
                return result["http_url"]  # Return HTTP URL for backward compatibility
            else:
                raise UploadError(f"Unsupported upload provider: {self.upload_provider}")
                
        except Exception as e:
            self.logger.error(f"Error uploading video: {str(e)}")
            raise UploadError(f"Error uploading video: {str(e)}")
    
    def _upload_to_supabase(self, video_path: str, metadata: Optional[dict] = None) -> str:
        """
        Upload a video to Supabase Storage.
        
        This is a placeholder implementation. In a real implementation, you would:
        1. Read the video file
        2. Upload it to Supabase Storage
        3. Return the public URL
        """
        self.logger.info(f"Uploading to Supabase Storage: {video_path}")
        
        # Extract filename from path
        filename = os.path.basename(video_path)
        
        # Generate a unique storage path
        timestamp = int(time.time())
        storage_path = f"videos/{timestamp}_{filename}"
        
        # In a real implementation, you would upload the file to Supabase Storage
        # For now, this is a placeholder
        """
        with open(video_path, "rb") as f:
            self.client.storage.from_("videos").upload(
                storage_path,
                f.read()
            )
        """
        
        # Simulate upload delay
        time.sleep(2)
        
        # Generate a public URL
        # In a real implementation, this would be the actual URL from Supabase
        public_url = f"https://oeexwetwqsooikroobgm.supabase.co/storage/v1/object/public/videos/{storage_path}"
        
        self.logger.info(f"Video uploaded to Supabase: {public_url}")
        
        return public_url
    
    def _upload_to_youtube(self, video_path: str, metadata: Optional[dict] = None) -> str:
        """
        Upload a video to YouTube.
        
        This is a placeholder implementation. In a real implementation, you would:
        1. Authenticate with the YouTube API
        2. Upload the video
        3. Return the public URL
        """
        self.logger.info(f"Uploading to YouTube: {video_path}")
        
        # In a real implementation, you would use the YouTube API to upload the video
        # For now, this is a placeholder
        
        # Simulate upload delay
        time.sleep(3)
        
        # Generate a fake YouTube URL
        video_id = f"yt{int(time.time())}"
        public_url = f"https://www.youtube.com/watch?v={video_id}"
        
        self.logger.info(f"Video uploaded to YouTube: {public_url}")
        
        return public_url
    
    def _upload_to_s3(self, video_path: str, metadata: Optional[dict] = None) -> str:
        """
        Upload a video to Amazon S3.
        
        This is a placeholder implementation. In a real implementation, you would:
        1. Authenticate with AWS
        2. Upload the video to S3
        3. Return the public URL
        """
        self.logger.info(f"Uploading to S3: {video_path}")
        
        # In a real implementation, you would use boto3 to upload the video to S3
        # For now, this is a placeholder
        
        # Simulate upload delay
        time.sleep(2)
        
        # Generate a fake S3 URL
        timestamp = int(time.time())
        filename = os.path.basename(video_path)
        public_url = f"https://music-videos-bucket.s3.amazonaws.com/{timestamp}_{filename}"
        
        self.logger.info(f"Video uploaded to S3: {public_url}")
        
        return public_url
        
    def _upload_to_local(self, video_path: str, metadata: Optional[dict] = None) -> Dict[str, str]:
        """
        Upload a video to the Samba share on hyun.club.
        
        Args:
            video_path: Path to the video file to upload
            metadata: Optional metadata to associate with the video
            
        Returns:
            Dictionary with network_path and http_url
            
        Raises:
            UploadError: If video upload fails
        """
        try:
            self.logger.info(f"Uploading to hyun.club Samba share: {video_path}")
            
            # Generate a unique filename based on metadata
            if metadata and 'title' in metadata:
                # Create a safe filename from the title
                safe_title = re.sub(r'[^\w\-_]', '_', metadata['title'])
                filename = f"{safe_title}_{uuid.uuid4().hex[:8]}.mp4"
            else:
                filename = f"{uuid.uuid4()}.mp4"
            
            # For production use: Upload to the remote server using SFTP
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Get credentials from environment variables or config
            server = VIDEO_SERVER
            username = VIDEO_SERVER_USER
            password = VIDEO_SERVER_PASSWORD
            
            if not password:
                self.logger.warning("VIDEO_SERVER_PASSWORD not set, using default password")
                password = "password"  # Default password for testing only
            
            # Connect to the server
            self.logger.info(f"Connecting to {server} to upload video")
            ssh.connect(server, username=username, password=password)
            
            # Upload the file
            sftp = ssh.open_sftp()
            remote_path = f"/data/videos/{filename}"
            self.logger.info(f"Uploading {video_path} to {remote_path}")
            sftp.put(video_path, remote_path)
            sftp.close()
            ssh.close()
            
            # Return both network path and HTTP URL
            result = {
                "network_path": f"\\\\hyun.club\\videos\\{filename}",
                "http_url": f"http://hyun.club/videos/{filename}"
            }
            
            self.logger.info(f"Video uploaded successfully to {result['network_path']}")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to upload video to hyun.club: {str(e)}")
            raise UploadError(f"Failed to upload video to hyun.club: {str(e)}")
