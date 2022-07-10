import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { map } from 'rxjs/operators';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { AbstractNameFilterService } from './abstract-name-filter-service';
import { CategoryService } from './category.service';

@Injectable({
  providedIn: 'root'
})
export class CorrespondentService extends AbstractNameFilterService<PaperlessCorrespondent> {

  constructor(http: HttpClient, private categoryService: CategoryService) {
    super(http, 'correspondents')
  }

  listFiltered(page?: number, pageSize?: number, sortField?: string, sortReverse?: boolean, nameFilter?: string) {
    let params = {}
    if (nameFilter) {
      params = {'name__icontains': nameFilter}
    }
    return this.list(page, pageSize, sortField, sortReverse, params).pipe(
      map(results => {
        results.results.forEach(corr => this.addObservablesToCorrespondent(corr))
        return results
      })
    )
  }

  addObservablesToCorrespondent(corr: PaperlessCorrespondent) {
    if (corr.category) {
      corr.category$ = this.categoryService.getCached(corr.category)
    }
    return corr
  }
}
