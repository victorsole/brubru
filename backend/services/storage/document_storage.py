"""
Document Storage Service

Manages storage and retrieval of uploaded documents.
Uses filesystem storage with optional future Supabase integration.
"""

import logging
import uuid
import shutil
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime
import json

logger = logging.getLogger(__name__)


class DocumentStorage:
    """
    Store and retrieve uploaded documents.

    Storage structure:
    - uploads/
      - {document_id}/
        - original.{ext}  # Original uploaded file
        - metadata.json   # Document metadata
        - processed.json  # Processed content
    """

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize document storage.

        Args:
            base_path: Base directory for storage (default: ./uploads)
        """
        self.base_path = base_path or Path("uploads")
        self.base_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initialized DocumentStorage at: {self.base_path}")

    def store_document(
        self,
        file_content: bytes,
        filename: str,
        content_type: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Store uploaded document.

        Args:
            file_content: File content as bytes
            filename: Original filename
            content_type: MIME type
            user_id: User ID (optional)
            metadata: Additional metadata

        Returns:
            document_id: Unique document ID
        """
        try:
            # Generate unique document ID
            document_id = str(uuid.uuid4())

            # Create document directory
            doc_dir = self.base_path / document_id
            doc_dir.mkdir(parents=True, exist_ok=True)

            # Get file extension
            file_ext = Path(filename).suffix

            # Save original file
            original_path = doc_dir / f"original{file_ext}"
            with open(original_path, 'wb') as f:
                f.write(file_content)

            # Create metadata
            doc_metadata = {
                'document_id': document_id,
                'filename': filename,
                'content_type': content_type,
                'file_size': len(file_content),
                'file_extension': file_ext,
                'user_id': user_id,
                'created_at': datetime.now().isoformat(),
                'status': 'uploaded',
                'custom_metadata': metadata or {}
            }

            # Save metadata
            metadata_path = doc_dir / 'metadata.json'
            with open(metadata_path, 'w') as f:
                json.dump(doc_metadata, f, indent=2)

            logger.info(
                f"Stored document {document_id}: {filename} "
                f"({len(file_content)} bytes)"
            )

            return document_id

        except Exception as e:
            logger.error(f"Error storing document: {str(e)}")
            raise

    def store_processed_content(
        self,
        document_id: str,
        processed_content: Dict[str, Any]
    ) -> None:
        """
        Store processed document content.

        Args:
            document_id: Document ID
            processed_content: Processed content from PDF/DOCX processor
        """
        try:
            doc_dir = self.base_path / document_id

            if not doc_dir.exists():
                raise ValueError(f"Document {document_id} not found")

            # Save processed content
            processed_path = doc_dir / 'processed.json'
            with open(processed_path, 'w') as f:
                json.dump(processed_content, f, indent=2)

            # Update metadata status
            self._update_metadata(document_id, {'status': 'processed'})

            logger.info(f"Stored processed content for document {document_id}")

        except Exception as e:
            logger.error(f"Error storing processed content: {str(e)}")
            raise

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get document metadata and content.

        Args:
            document_id: Document ID

        Returns:
            Dict with metadata and content, or None if not found
        """
        try:
            doc_dir = self.base_path / document_id

            if not doc_dir.exists():
                logger.warning(f"Document {document_id} not found")
                return None

            # Load metadata
            metadata_path = doc_dir / 'metadata.json'
            if not metadata_path.exists():
                return None

            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            # Load processed content if available
            processed_path = doc_dir / 'processed.json'
            processed_content = None

            if processed_path.exists():
                with open(processed_path, 'r') as f:
                    processed_content = json.load(f)

            # Get original file path
            file_ext = metadata.get('file_extension', '')
            original_path = doc_dir / f"original{file_ext}"

            return {
                **metadata,
                'original_file_path': str(original_path) if original_path.exists() else None,
                'processed_content': processed_content,
                'has_processed_content': processed_content is not None
            }

        except Exception as e:
            logger.error(f"Error getting document {document_id}: {str(e)}")
            return None

    def get_document_content(self, document_id: str) -> Optional[bytes]:
        """
        Get original document file content.

        Args:
            document_id: Document ID

        Returns:
            File content as bytes, or None if not found
        """
        try:
            doc_dir = self.base_path / document_id

            if not doc_dir.exists():
                return None

            # Find original file
            original_files = list(doc_dir.glob("original.*"))

            if not original_files:
                return None

            with open(original_files[0], 'rb') as f:
                return f.read()

        except Exception as e:
            logger.error(f"Error getting document content: {str(e)}")
            return None

    def delete_document(self, document_id: str) -> bool:
        """
        Delete document and all associated files.

        Args:
            document_id: Document ID

        Returns:
            True if deleted, False if not found
        """
        try:
            doc_dir = self.base_path / document_id

            if not doc_dir.exists():
                logger.warning(f"Document {document_id} not found for deletion")
                return False

            # Delete entire directory
            shutil.rmtree(doc_dir)

            logger.info(f"Deleted document {document_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting document {document_id}: {str(e)}")
            return False

    def list_documents(
        self,
        user_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List documents.

        Args:
            user_id: Filter by user ID (optional)
            limit: Maximum number of documents

        Returns:
            List of document metadata
        """
        try:
            documents = []

            # Iterate through document directories
            for doc_dir in self.base_path.iterdir():
                if not doc_dir.is_dir():
                    continue

                metadata_path = doc_dir / 'metadata.json'
                if not metadata_path.exists():
                    continue

                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)

                # Filter by user_id if provided
                if user_id and metadata.get('user_id') != user_id:
                    continue

                documents.append(metadata)

                if len(documents) >= limit:
                    break

            # Sort by created_at (most recent first)
            documents.sort(
                key=lambda x: x.get('created_at', ''),
                reverse=True
            )

            return documents

        except Exception as e:
            logger.error(f"Error listing documents: {str(e)}")
            return []

    def _update_metadata(self, document_id: str, updates: Dict[str, Any]) -> None:
        """Update document metadata"""
        try:
            doc_dir = self.base_path / document_id
            metadata_path = doc_dir / 'metadata.json'

            if not metadata_path.exists():
                raise ValueError(f"Metadata not found for document {document_id}")

            # Load existing metadata
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            # Update
            metadata.update(updates)
            metadata['updated_at'] = datetime.now().isoformat()

            # Save
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

        except Exception as e:
            logger.error(f"Error updating metadata: {str(e)}")
            raise


# Global singleton
_document_storage: Optional[DocumentStorage] = None


def get_document_storage(base_path: Optional[Path] = None) -> DocumentStorage:
    """Get global document storage instance"""
    global _document_storage

    if _document_storage is None:
        _document_storage = DocumentStorage(base_path)

    return _document_storage
