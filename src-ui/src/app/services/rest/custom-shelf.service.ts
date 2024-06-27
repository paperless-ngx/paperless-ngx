import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { AbstractPaperlessService } from "./abstract-paperless-service";
import { AbstractNameFilterService } from "./abstract-name-filter-service";
import { CustomField } from "src/app/data/custom-field";
import { Shelf } from "src/app/data/custom-shelf";

@Injectable({
    providedIn: 'root',
})
export class CustomShelfService extends AbstractNameFilterService<Shelf> {
    constructor(http: HttpClient) {
        super(http, 'warehouses')
    }
}