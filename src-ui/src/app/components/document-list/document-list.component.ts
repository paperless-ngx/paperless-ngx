import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { cloneFilterRules, FilterRule } from 'src/app/data/filter-rule';
import { SavedViewConfig } from 'src/app/data/saved-view-config';
import { DocumentListViewService, SORT_FIELDS } from 'src/app/services/document-list-view.service';
import { SavedViewConfigService } from 'src/app/services/saved-view-config.service';
import { SaveViewConfigDialogComponent } from './save-view-config-dialog/save-view-config-dialog.component';

@Component({
  selector: 'app-document-list',
  templateUrl: './document-list.component.html',
  styleUrls: ['./document-list.component.css']
})
export class DocumentListComponent implements OnInit {

  constructor(
    public docs: DocumentListViewService,
    public savedViewConfigService: SavedViewConfigService,
    public route: ActivatedRoute,
    public modalService: NgbModal) { }

  displayMode = 'smallCards' // largeCards, smallCards, details

  filterRules: FilterRule[] = []
  showFilter = false

  getSortFields() {
    return SORT_FIELDS
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
    this.route.paramMap.subscribe(params => {
      if (params.has('id')) {
        this.docs.viewConfig = this.savedViewConfigService.getConfig(params.get('id'))
      } else {
        this.filterRules = cloneFilterRules(this.docs.currentFilterRules)
        this.showFilter = this.filterRules.length > 0
        this.docs.viewConfig = null
      }
      this.reload()
    })
  }

  reload() {
    this.docs.reload()
  }

  applyFilterRules() {
    this.docs.setFilterRules(this.filterRules)
    this.reload()
  }

  loadViewConfig(config: SavedViewConfig) {
    this.filterRules = cloneFilterRules(config.filterRules)
    this.docs.setFilterRules(config.filterRules)
    this.docs.currentSortField = config.sortField
    this.docs.currentSortDirection = config.sortDirection
    this.reload()
  }

  saveViewConfig() {
    let modal = this.modalService.open(SaveViewConfigDialogComponent, {backdrop: 'static'})
    modal.componentInstance.saveClicked.subscribe(formValue => {
      this.savedViewConfigService.saveConfig({
        filterRules: cloneFilterRules(this.filterRules),
        title: formValue.title,
        showInDashboard: formValue.showInDashboard,
        showInSideBar: formValue.showInSideBar,
        sortDirection: this.docs.currentSortDirection,
        sortField: this.docs.currentSortField
      })
      modal.close()
    })
  }
}
