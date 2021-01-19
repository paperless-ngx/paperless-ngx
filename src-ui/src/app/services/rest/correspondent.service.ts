import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { AbstractNameFilterService } from './abstract-name-filter-service';

@Injectable({
  providedIn: 'root'
})
export class CorrespondentService extends AbstractNameFilterService<PaperlessCorrespondent> {

  constructor(http: HttpClient) {
    super(http, 'correspondents')
  }

}
