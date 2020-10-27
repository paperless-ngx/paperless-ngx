import { Component, OnInit } from '@angular/core';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { FilterRuleSet } from '../filter-editor/filter-editor.component';

@Component({
  selector: 'app-document-list',
  templateUrl: './document-list.component.html',
  styleUrls: ['./document-list.component.css']
})
export class DocumentListComponent implements OnInit {

  constructor(
    public docs: DocumentListViewService) { }

  displayMode = 'smallCards' // largeCards, smallCards, details

  filter = new FilterRuleSet()
  showFilter = false

  getSortFields() {
    return DocumentListViewService.SORT_FIELDS
  }

  setSort(field: string) {
    this.docs.currentSortField = field
    this.reload()
  }

  saveDisplayMode() {
    localStorage.setItem('document-list:displayMode', this.displayMode)
  }

  ngOnInit(): void {
    if (localStorage.getItem('document-list:displayMode') != null) {
      this.displayMode = localStorage.getItem('document-list:displayMode')
    }
    this.filter = this.docs.currentFilter.clone()
    this.showFilter = this.filter.rules.length > 0
    this.reload()
  }

  reload() {
    this.docs.reload()
  }

  applyFilter() {
    this.docs.setFilter(this.filter.clone())
    this.reload()
  }

}
