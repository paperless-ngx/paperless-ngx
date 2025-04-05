import { Injectable } from '@angular/core'
import { MarkedOptions, MarkedRenderer } from 'ngx-markdown'
import { environment } from 'src/environments/environment'
import { DocumentService } from './rest/document.service'

@Injectable({ providedIn: 'root' })
export class MarkdownConfigService {
  private currentDocumentId: number = null;

  constructor(private documentService: DocumentService) { }

  /**
   * Set the current document ID for image resolution
   */
  public setCurrentDocumentId(documentId: number) {
    this.currentDocumentId = documentId;
  }

  /**
   * Creates a custom renderer that handles OCR image references
   */
  public createMarkedOptions(): MarkedOptions {
    const renderer = new MarkedRenderer()
    const originalImageRenderer = renderer.image;

    // Override the image renderer
    renderer.image = (imageInfo) => {

      if (imageInfo.href.includes('OCR_IMAGE:') && this.currentDocumentId) {
        // e.g.: imageInfo = '[OCR_IMAGE:0]'
        // extract the 0 from the string
        const imageIndex = imageInfo.href.split(':')[1].replace(']', '');
        // Use DocumentService to get OCR image URL
        imageInfo.href = this.documentService.getOcrImageUrl(this.currentDocumentId, parseInt(imageIndex));
      }
      return originalImageRenderer.call(renderer, imageInfo);
    };

    return {
      renderer: renderer,
      gfm: true,
      breaks: false,
      pedantic: false
    }
  }
}
