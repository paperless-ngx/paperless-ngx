import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { AbstractNameFilterService } from './abstract-name-filter-service';

@Injectable({
  providedIn: 'root'
})
export class TagService extends AbstractNameFilterService<PaperlessTag> {

  constructor(http: HttpClient) {
    super(http, 'tags')
  }
}
