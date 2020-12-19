import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { AbstractPaperlessService } from './abstract-paperless-service';

@Injectable({
  providedIn: 'root'
})
export class CorrespondentService extends AbstractPaperlessService<PaperlessCorrespondent> {

  constructor(http: HttpClient) {
    super(http, 'correspondents')
  }

}
