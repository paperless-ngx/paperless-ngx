import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Warehouse } from 'src/app/data/warehouse'
import { AbstractNameFilterService } from './abstract-name-filter-service'
import { environment } from 'src/environments/environment';
import { Observable, first } from 'rxjs';
import { Results } from 'src/app/data/results';

@Injectable({
  providedIn: 'root',
})
export class WarehouseService extends AbstractNameFilterService<Warehouse> {
  constructor(http: HttpClient) {
    super(http, 'warehouses')
  }
  getWarehousePath(id: number): Observable<Warehouse> {
    return this.http.get<Warehouse>(this.getResourceUrl(id, 'warehouse_path'))
  }
}
