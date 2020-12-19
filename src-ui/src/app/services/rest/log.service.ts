import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { PaperlessLog } from 'src/app/data/paperless-log';
import { AbstractPaperlessService } from './abstract-paperless-service';

@Injectable({
  providedIn: 'root'
})
export class LogService extends AbstractPaperlessService<PaperlessLog> {

  constructor(http: HttpClient) {
    super(http, 'logs')
  }
}
