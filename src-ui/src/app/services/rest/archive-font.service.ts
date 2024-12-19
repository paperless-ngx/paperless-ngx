import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { DocumentType } from 'src/app/data/document-type'
import { AbstractNameFilterService } from './abstract-name-filter-service'
import { ArchiveFont } from '../../data/archive-font'

@Injectable({
  providedIn: 'root',
})
export class ArchiveFontService extends AbstractNameFilterService<ArchiveFont> {
  constructor(http: HttpClient) {
    super(http, 'archive_fonts')
  }
}

