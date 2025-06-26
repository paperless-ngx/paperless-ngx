import { HttpClient } from '@angular/common/http'
import { Injectable, inject } from '@angular/core'
import { Tag } from 'src/app/data/tag'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class TagService extends AbstractNameFilterService<Tag> {
  constructor() {
    const http = inject(HttpClient)

    super(http, 'tags')
  }
}
