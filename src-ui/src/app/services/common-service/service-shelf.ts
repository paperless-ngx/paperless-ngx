import { HttpClient, HttpParams } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";
import { environment } from "src/environments/environment";



@Injectable({
    providedIn: 'root',
})
export class CustomService {
    [x: string]: any;
    protected baseUrl: string = environment.apiBaseUrl


    constructor(private http: HttpClient) { }

    private getOrderingQueryParam(sortField: string, sortReverse: boolean) {
        if (sortField) {
            return (sortReverse ? '-' : '') + sortField
        } else {
            return null
        }
    }

    getDocuments(id: any, page?: number,
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
        //httpParams = httpParams.set('parent_warehouse', id);
        return this.http.get<any>(`${this.baseUrl}warehouses/?parent_warehouse=${id}`, {
            params: httpParams,
        });
    }

    getWarehouses(): Observable<any> {
        return this.http.get<any>(`${this.baseUrl}warehouses/`);
    }

    getShelf(): Observable<any> {
        return this.http.get<any>(`${this.baseUrl}warehouses/`);
    }


    getShelfId(id: any): Observable<any> {
        return this.http.get<any>(`${this.baseUrl}warehouses/?parent_warehouse=${id}`)
    }


}