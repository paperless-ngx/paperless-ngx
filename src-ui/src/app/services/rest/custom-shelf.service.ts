import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { AbstractPaperlessService } from './abstract-paperless-service'
import { AbstractNameFilterService } from './abstract-name-filter-service'
import { CustomField } from 'src/app/data/custom-field'
import { Shelf } from 'src/app/data/custom-shelf'
import { Observable } from 'rxjs'
import { Warehouse } from '../../data/warehouse'

@Injectable({
  providedIn: 'root',
})
export class CustomShelfService extends AbstractNameFilterService<Shelf> {
  constructor(http: HttpClient) {
    super(http, 'warehouses')
  }

  getWarehousePath(id: number): Observable<Shelf> {
    return this.http.get<Shelf>(this.getResourceUrl(id, 'warehouse_path'))
  }

}
