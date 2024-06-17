import { Injectable } from "@angular/core";
import { AbstractNameFilterService } from "./abstract-name-filter-service";
import { HttpClient } from "@angular/common/http";
import { Box } from "src/app/data/box";

@Injectable({
    providedIn: 'root',
})
export class BoxService extends AbstractNameFilterService<Box> {
    constructor(http: HttpClient) {
        super(http, 'warehouses')
    }
}