import { HttpClient } from '@angular/common/http'
import { Injectable } from '@angular/core'
import { Warehouse } from 'src/app/data/warehouse'
import { AbstractNameFilterService } from './abstract-name-filter-service'

@Injectable({
  providedIn: 'root',
})
export class WarehouseService extends AbstractNameFilterService<Warehouse> {
  constructor(http: HttpClient) {
    super(http, 'warehouses')
  }
}
