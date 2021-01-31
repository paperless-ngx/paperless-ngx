import { HttpClient } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from 'src/environments/environment';

export interface Statistics {
  documents_total?: number
  documents_inbox?: number
}


@Component({
  selector: 'app-statistics-widget',
  templateUrl: './statistics-widget.component.html',
  styleUrls: ['./statistics-widget.component.scss']
})
export class StatisticsWidgetComponent implements OnInit {

  constructor(private http: HttpClient) { }

  statistics: Statistics = {}

  getStatistics(): Observable<Statistics> {
    return this.http.get(`${environment.apiBaseUrl}statistics/`)
  }

  ngOnInit(): void {
    this.getStatistics().subscribe(statistics => {
      this.statistics = statistics
    })
  }

}
