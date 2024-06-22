import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { AbstractPaperlessService } from "./abstract-paperless-service";
import { CustomFields } from "src/app/data/customfields";
import { AbstractNameFilterService } from "./abstract-name-filter-service";
import { CustomField } from "src/app/data/custom-field";

@Injectable({
    providedIn: 'root',
})
export class CustomShelfService extends AbstractNameFilterService<CustomFields> {
    constructor(http: HttpClient) {
        super(http, 'warehouses')
    }
}