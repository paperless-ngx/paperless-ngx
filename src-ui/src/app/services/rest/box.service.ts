import { Injectable } from "@angular/core";
import { AbstractNameFilterService } from "./abstract-name-filter-service";
import { HttpClient } from "@angular/common/http";
import { Box } from "src/app/data/box";
import { Observable } from 'rxjs'
import { Shelf } from '../../data/custom-shelf'

@Injectable({
    providedIn: 'root',
})
export class BoxService extends AbstractNameFilterService<Box> {
    [x: string]: any;
    constructor(http: HttpClient) {
        super(http, 'warehouses')
    }
    getWarehousePath(id: number): Observable<Shelf> {
    return this.http.get<Shelf>(this.getResourceUrl(id, 'warehouse_path'))
  }
}
