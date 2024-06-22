import { HttpClient } from "@angular/common/http";
import { Injectable } from "@angular/core";
import { Observable } from "rxjs";
import { environment } from "src/environments/environment";



@Injectable({
    providedIn: 'root',
})
export class CustomService {
    protected baseUrl: string = environment.apiBaseUrl


    constructor(private http: HttpClient) { }

    getDocuments(id: any): Observable<any> {
        console.log('dqwwqdwq', id)
        return this.http.get<any>(`${this.baseUrl}warehouses/?parent_warehouse=${id}`);
    }
}