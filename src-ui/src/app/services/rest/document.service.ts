import { Injectable } from '@angular/core';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { AbstractPaperlessService } from './abstract-paperless-service';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { AuthService } from '../auth.service';

@Injectable({
  providedIn: 'root'
})
export class DocumentService extends AbstractPaperlessService<PaperlessDocument> {

  constructor(http: HttpClient, private auth: AuthService) {
    super(http, 'documents')
  }

  getPreviewUrl(id: number): string {
    return this.getResourceUrl(id, 'preview') + `?auth_token=${this.auth.getToken()}`
  }

  getThumbUrl(id: number): string {
    return this.getResourceUrl(id, 'thumb') + `?auth_token=${this.auth.getToken()}`
  }

  getDownloadUrl(id: number): string {
    return this.getResourceUrl(id, 'download') + `?auth_token=${this.auth.getToken()}`
  }

  uploadDocument(formData) {
    return this.http.post(this.getResourceUrl(null, 'post_document'), formData)
  }

}
