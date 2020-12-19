import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { AbstractPaperlessService } from './abstract-paperless-service';

@Injectable({
  providedIn: 'root'
})
export class TagService extends AbstractPaperlessService<PaperlessTag> {

  constructor(http: HttpClient) {
    super(http, 'tags')
  }
}
