import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { PaperlessCategory } from 'src/app/data/paperless-category';
import { AbstractNameFilterService } from './abstract-name-filter-service';

@Injectable({
  providedIn: 'root'
})
export class CategoryService extends AbstractNameFilterService<PaperlessCategory> {

  constructor(http: HttpClient) {
    super(http, 'categories')
  }

}
