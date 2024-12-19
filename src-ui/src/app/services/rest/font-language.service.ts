
import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { DocumentType } from 'src/app/data/document-type'
import { AbstractNameFilterService } from './abstract-name-filter-service'
import { ArchiveFont } from '../../data/archive-font'
import { FontLanguage } from '../../data/font-language'

@Injectable({
  providedIn: 'root',
})
export class FontLanguageService extends AbstractNameFilterService<FontLanguage> {
  constructor(http: HttpClient) {
    super(http, 'font_languages')
  }
}
