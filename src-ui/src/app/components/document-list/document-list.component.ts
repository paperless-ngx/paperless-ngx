import { Component, OnInit } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { cloneFilterRules, FilterRule } from 'src/app/data/filter-rule';
import { SavedViewConfig } from 'src/app/data/saved-view-config';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { DOCUMENT_SORT_FIELDS } from 'src/app/services/rest/document.service';
import { SavedViewConfigService } from 'src/app/services/saved-view-config.service';
import { SaveViewConfigDialogComponent } from './save-view-config-dialog/save-view-config-dialog.component';

@Component({
  selector: 'app-document-list',
  templateUrl: './document-list.component.html',
  styleUrls: ['./document-list.component.scss']
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

  getTitle() {
    return this.docs.viewConfigOverride ? this.docs.viewConfigOverride.title : "Documents"
  }

  getSortFields() {
    return DOCUMENT_SORT_FIELDS
  }

  setSort(field: string) {
    this.docs.sortField = field
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
        this.docs.viewConfigOverride = this.savedViewConfigService.getConfig(params.get('id'))
      } else {
        this.filterRules = this.docs.filterRules
        this.showFilter = this.filterRules.length > 0
        this.docs.viewConfigOverride = null
      }
      this.reload()
    })
  }

  reload() {
    this.docs.reload()
  }

  applyFilterRules() {
    this.docs.filterRules = this.filterRules
  }

  loadViewConfig(config: SavedViewConfig) {
    this.filterRules = cloneFilterRules(config.filterRules)
    this.docs.loadViewConfig(config)
  }

  saveViewConfig() {
    let modal = this.modalService.open(SaveViewConfigDialogComponent, {backdrop: 'static'})
    modal.componentInstance.saveClicked.subscribe(formValue => {
      this.savedViewConfigService.saveConfig({
        title: formValue.title,
        showInDashboard: formValue.showInDashboard,
        showInSideBar: formValue.showInSideBar,
        filterRules: this.docs.filterRules,
        sortDirection: this.docs.sortDirection,
        sortField: this.docs.sortField
      })
      modal.close()
    })
  }
}
