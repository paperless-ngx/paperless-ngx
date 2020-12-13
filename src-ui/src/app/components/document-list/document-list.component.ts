import { Component, OnInit, ViewChild } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { ActivatedRoute } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { cloneFilterRules, FilterRule } from 'src/app/data/filter-rule';
import { FILTER_CORRESPONDENT, FILTER_DOCUMENT_TYPE, FILTER_HAS_TAG, FILTER_RULE_TYPES } from 'src/app/data/filter-rule-type';
import { SavedViewConfig } from 'src/app/data/saved-view-config';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { FilterEditorViewService } from 'src/app/services/filter-editor-view.service';
import { DOCUMENT_SORT_FIELDS } from 'src/app/services/rest/document.service';
import { SavedViewConfigService } from 'src/app/services/saved-view-config.service';
import { Toast, ToastService } from 'src/app/services/toast.service';
import { environment } from 'src/environments/environment';
import { SaveViewConfigDialogComponent } from './save-view-config-dialog/save-view-config-dialog.component';
import { FilterEditorComponent } from 'src/app/components/filter-editor/filter-editor.component';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';

@Component({
  selector: 'app-document-list',
  templateUrl: './document-list.component.html',
  styleUrls: ['./document-list.component.scss']
})
export class DocumentListComponent implements OnInit {

  constructor(
    public list: DocumentListViewService,
    public savedViewConfigService: SavedViewConfigService,
    public filterEditorService: FilterEditorViewService,
    public route: ActivatedRoute,
    private toastService: ToastService,
    public modalService: NgbModal,
    private titleService: Title) { }

  displayMode = 'smallCards' // largeCards, smallCards, details

  get isFiltered() {
    return this.list.filterRules?.length > 0
  }

  set filterRules(filterRules: FilterRule[]) {
    this.filterEditorService.filterRules = filterRules
  }

  get filterRules(): FilterRule[] {
    return this.filterEditorService.filterRules
  }

  getTitle() {
    return this.list.savedViewTitle || "Documents"
  }

  getSortFields() {
    return DOCUMENT_SORT_FIELDS
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
        this.list.savedView = this.savedViewConfigService.getConfig(params.get('id'))
        this.filterEditorService.filterRules = this.list.filterRules
        this.titleService.setTitle(`${this.list.savedView.title} - ${environment.appTitle}`)
      } else {
        this.list.savedView = null
        this.filterEditorService.filterRules = this.list.filterRules
        this.titleService.setTitle(`Documents - ${environment.appTitle}`)
      }
      this.list.clear()
      this.list.reload()
    })
    this.filterEditorService.filterRules = this.list.filterRules
  }

  applyFilterRules() {
    this.list.filterRules = this.filterEditorService.filterRules
  }

  clearFilterRules() {
    this.list.filterRules = this.filterEditorService.filterRules
  }

  loadViewConfig(config: SavedViewConfig) {
    this.filterEditorService.filterRules = cloneFilterRules(config.filterRules)
    this.list.load(config)
  }

  saveViewConfig() {
    this.savedViewConfigService.updateConfig(this.list.savedView)
    this.toastService.showToast(Toast.make("Information", `View "${this.list.savedView.title}" saved successfully.`))
  }

  saveViewConfigAs() {
    let modal = this.modalService.open(SaveViewConfigDialogComponent, {backdrop: 'static'})
    modal.componentInstance.saveClicked.subscribe(formValue => {
      this.savedViewConfigService.newConfig({
        title: formValue.title,
        showInDashboard: formValue.showInDashboard,
        showInSideBar: formValue.showInSideBar,
        filterRules: this.list.filterRules,
        sortDirection: this.list.sortDirection,
        sortField: this.list.sortField
      })
      modal.close()
    })
  }

  clickTag(tagID: number) {
    this.filterEditorService.toggleFitlerByTagID(tagID)
    this.applyFilterRules()
  }

  clickCorrespondent(correspondentID: number) {
    this.filterEditorService.toggleFitlerByCorrespondentID(correspondentID)
    this.applyFilterRules()
  }

  clickDocumentType(documentTypeID: number) {
    this.filterEditorService.toggleFitlerByDocumentTypeID(documentTypeID)
    this.applyFilterRules()
  }

}
