"""
MCP tools for document management in Paperless-ngx
"""
from typing import List, Dict, Any, Optional
from django_mcp import mcp_app as mcp
from mcp.server.fastmcp import Context

from documents.models import Document, Correspondent, DocumentType, Tag
from django.contrib.auth.models import User
from django.db.models import Q
from asgiref.sync import sync_to_async


@mcp.tool()
async def search_documents(query: str, ctx: Context, limit: int = 10) -> Dict[str, Any]:
    """
    Search documents by content or metadata.
    
    Args:
        query: Search query string
        limit: Maximum number of results to return (default: 10)
        
    Returns:
        Dictionary with search results including document metadata
    """
    try:
        await ctx.info(f"Searching for documents matching: {query}")
        
        # Search in title, content, and original filename
        documents = await sync_to_async(list)(
            Document.objects.filter(
                Q(title__icontains=query) |
                Q(content__icontains=query) |
                Q(original_filename__icontains=query)
            ).select_related('correspondent', 'document_type')
            .prefetch_related('tags')[:limit]
        )
        
        results = []
        for doc in documents:
            doc_data = {
                'id': doc.id,
                'title': doc.title,
                'created': doc.created.isoformat() if doc.created else None,
                'correspondent': doc.correspondent.name if doc.correspondent else None,
                'document_type': doc.document_type.name if doc.document_type else None,
                'tags': [tag.name for tag in doc.tags.all()],
                'original_filename': doc.original_filename,
                'archive_serial_number': doc.archive_serial_number,
            }
            results.append(doc_data)
        
        await ctx.info(f"Found {len(results)} documents")
        
        return {
            'total_found': len(results),
            'query': query,
            'documents': results
        }
        
    except Exception as e:
        await ctx.error(f"Error searching documents: {str(e)}")
        return {'error': str(e), 'documents': []}


@mcp.tool()
async def get_document_details(document_id: int, ctx: Context) -> Dict[str, Any]:
    """
    Get detailed information about a specific document.
    
    Args:
        document_id: The ID of the document to retrieve
        
    Returns:
        Dictionary with detailed document information
    """
    try:
        await ctx.info(f"Retrieving details for document ID: {document_id}")
        
        document = await Document.objects.select_related(
            'correspondent', 'document_type', 'storage_path'
        ).prefetch_related('tags', 'custom_fields').aget(id=document_id)
        
        # Get custom fields
        custom_fields = []
        async for cf_instance in document.custom_fields.select_related('field').all():
            custom_fields.append({
                'name': cf_instance.field.name,
                'value': cf_instance.value,
                'data_type': cf_instance.field.data_type
            })
        
        result = {
            'id': document.id,
            'title': document.title,
            'content': document.content[:500] + '...' if len(document.content) > 500 else document.content,
            'created': document.created.isoformat() if document.created else None,
            'added': document.added.isoformat() if document.added else None,
            'modified': document.modified.isoformat() if document.modified else None,
            'correspondent': document.correspondent.name if document.correspondent else None,
            'document_type': document.document_type.name if document.document_type else None,
            'storage_path': document.storage_path.path if document.storage_path else None,
            'tags': [tag.name for tag in document.tags.all()],
            'archive_serial_number': document.archive_serial_number,
            'original_filename': document.original_filename,
            'checksum': document.checksum,
            'mime_type': document.mime_type,
            'page_count': document.page_count,
            'custom_fields': custom_fields
        }
        
        await ctx.info("Document details retrieved successfully")
        return result
        
    except Document.DoesNotExist:
        await ctx.error(f"Document with ID {document_id} not found")
        return {'error': f'Document with ID {document_id} not found'}
    except Exception as e:
        await ctx.error(f"Error retrieving document details: {str(e)}")
        return {'error': str(e)}


@mcp.tool()
async def list_documents(ctx: Context, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
    """
    List documents with pagination.
    
    Args:
        limit: Maximum number of documents to return (default: 20)
        offset: Number of documents to skip (default: 0)
        
    Returns:
        Dictionary with paginated document list
    """
    try:
        await ctx.info(f"Listing documents (limit: {limit}, offset: {offset})")
        
        documents = await sync_to_async(list)(
            Document.objects.select_related('correspondent', 'document_type')
            .prefetch_related('tags')
            .order_by('-added')[offset:offset + limit]
        )
        
        total_count = await Document.objects.acount()
        
        results = []
        for doc in documents:
            doc_data = {
                'id': doc.id,
                'title': doc.title,
                'created': doc.created.isoformat() if doc.created else None,
                'added': doc.added.isoformat() if doc.added else None,
                'correspondent': doc.correspondent.name if doc.correspondent else None,
                'document_type': doc.document_type.name if doc.document_type else None,
                'tags': [tag.name for tag in doc.tags.all()],
                'archive_serial_number': doc.archive_serial_number,
            }
            results.append(doc_data)
        
        await ctx.info(f"Retrieved {len(results)} documents")
        
        return {
            'documents': results,
            'total_count': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': offset + limit < total_count
        }
        
    except Exception as e:
        await ctx.error(f"Error listing documents: {str(e)}")
        return {'error': str(e), 'documents': []}


@mcp.tool()
async def get_correspondents(ctx: Context) -> List[Dict[str, Any]]:
    """
    Get list of all correspondents.
    
    Returns:
        List of correspondent dictionaries
    """
    try:
        await ctx.info("Retrieving correspondents list")
        
        correspondents = await sync_to_async(list)(
            Correspondent.objects.all().order_by('name')
        )
        
        result = []
        for corr in correspondents:
            result.append({
                'id': corr.id,
                'name': corr.name,
                'slug': corr.slug,
                'matching_algorithm': corr.matching_algorithm,
                'match': corr.match,
                'is_insensitive': corr.is_insensitive
            })
        
        await ctx.info(f"Retrieved {len(result)} correspondents")
        return result
        
    except Exception as e:
        await ctx.error(f"Error retrieving correspondents: {str(e)}")
        return []


@mcp.tool()
async def get_document_types(ctx: Context) -> List[Dict[str, Any]]:
    """
    Get list of all document types.
    
    Returns:
        List of document type dictionaries
    """
    try:
        await ctx.info("Retrieving document types list")
        
        doc_types = await sync_to_async(list)(
            DocumentType.objects.all().order_by('name')
        )
        
        result = []
        for dt in doc_types:
            result.append({
                'id': dt.id,
                'name': dt.name,
                'slug': dt.slug,
                'matching_algorithm': dt.matching_algorithm,
                'match': dt.match,
                'is_insensitive': dt.is_insensitive
            })
        
        await ctx.info(f"Retrieved {len(result)} document types")
        return result
        
    except Exception as e:
        await ctx.error(f"Error retrieving document types: {str(e)}")
        return []


@mcp.tool()
async def get_tags(ctx: Context) -> List[Dict[str, Any]]:
    """
    Get list of all tags.
    
    Returns:
        List of tag dictionaries
    """
    try:
        await ctx.info("Retrieving tags list")
        
        tags = await sync_to_async(list)(
            Tag.objects.all().order_by('name')
        )
        
        result = []
        for tag in tags:
            result.append({
                'id': tag.id,
                'name': tag.name,
                'slug': tag.slug,
                'color': tag.color,
                'text_color': tag.text_color,
                'matching_algorithm': tag.matching_algorithm,
                'match': tag.match,
                'is_insensitive': tag.is_insensitive,
                'is_inbox_tag': tag.is_inbox_tag
            })
        
        await ctx.info(f"Retrieved {len(result)} tags")
        return result
        
    except Exception as e:
        await ctx.error(f"Error retrieving tags: {str(e)}")
        return []


@mcp.tool()
async def get_document_statistics(ctx: Context) -> Dict[str, Any]:
    """
    Get basic statistics about the document collection.
    
    Returns:
        Dictionary with collection statistics
    """
    try:
        await ctx.info("Calculating document statistics")
        
        total_documents = await Document.objects.acount()
        total_correspondents = await Correspondent.objects.acount()
        total_document_types = await DocumentType.objects.acount()
        total_tags = await Tag.objects.acount()
        
        # Get recent documents count (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.now() - timedelta(days=30)
        recent_documents = await Document.objects.filter(added__gte=thirty_days_ago).acount()
        
        result = {
            'total_documents': total_documents,
            'total_correspondents': total_correspondents,
            'total_document_types': total_document_types,
            'total_tags': total_tags,
            'recent_documents_30_days': recent_documents,
            'calculated_at': datetime.now().isoformat()
        }
        
        await ctx.info("Statistics calculated successfully")
        return result
        
    except Exception as e:
        await ctx.error(f"Error calculating statistics: {str(e)}")
        return {'error': str(e)}