import { HttpClient, HttpParams } from "@angular/common/http"
import { Injectable } from "@angular/core"
import { Observable } from "rxjs"
import { environment } from "src/environments/environment"


@Injectable({
    providedIn: 'root',
})
export class BoxsServices {
    protected baseUrl: string = environment.apiBaseUrl


    constructor(private http: HttpClient) { }

    private getOrderingQueryParam(sortField: string, sortReverse: boolean) {
        if (sortField) {
            return (sortReverse ? '-' : '') + sortField
        } else {
            return null
        }
    }

    getBox(id: any, page?: number,
        pageSize?: number,
        sortField?: string,
        sortReverse?: boolean): Observable<any> {
        let httpParams = new HttpParams()
        if (page) {
            httpParams = httpParams.set('page', page.toString())
        }
        if (pageSize) {
            httpParams = httpParams.set('page_size', pageSize.toString())
        }
        let ordering = this.getOrderingQueryParam(sortField, sortReverse)
        if (ordering) {
            httpParams = httpParams.set('ordering', ordering)
        }
        return this.http.get<any>(`${this.baseUrl}warehouses/?parent_warehouse=${id}`, {
            params: httpParams,
        });
    }
}