import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Tag } from 'src/app/data/tag'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class TagService extends AbstractNameFilterService<Tag> {
  constructor(http: HttpClient) {
    super(http, 'tags')
  }
}
