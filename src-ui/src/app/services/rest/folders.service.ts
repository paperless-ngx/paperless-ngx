import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Warehouse } from 'src/app/data/warehouse'
import { AbstractNameFilterService } from './abstract-name-filter-service';

@Injectable({
  providedIn: 'root'
})
export class FoldersService extends AbstractNameFilterService<folders> {
  constructor(http: HttpClient) {
    super(http, 'folders')
  }
}