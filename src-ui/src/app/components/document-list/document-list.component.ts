import { Component, OnInit, ViewChild } from '@angular/core';
import { Title } from '@angular/platform-browser';
import { ActivatedRoute } from '@angular/router';
import { NgbModal } from '@ng-bootstrap/ng-bootstrap';
import { cloneFilterRules, FilterRule } from 'src/app/data/filter-rule';
import { FILTER_CORRESPONDENT, FILTER_DOCUMENT_TYPE, FILTER_HAS_TAG, FILTER_RULE_TYPES } from 'src/app/data/filter-rule-type';
import { SavedViewConfig } from 'src/app/data/saved-view-config';
import { DocumentListViewService } from 'src/app/services/document-list-view.service';
import { DOCUMENT_SORT_FIELDS } from 'src/app/services/rest/document.service';
import { SavedViewConfigService } from 'src/app/services/saved-view-config.service';
import { Toast, ToastService } from 'src/app/services/toast.service';
import { environment } from 'src/environments/environment';
import { SaveViewConfigDialogComponent } from './save-view-config-dialog/save-view-config-dialog.component';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { TagService } from 'src/app/services/rest/tag.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { FilterEditorComponent } from 'src/app/components/filter-editor/filter-editor.component';

@Component({
  selector: 'app-document-list',
  templateUrl: './document-list.component.html',
  styleUrls: ['./document-list.component.scss']
})
export class DocumentListComponent implements OnInit {

  constructor(
    public list: DocumentListViewService,
    public savedViewConfigService: SavedViewConfigService,
    public route: ActivatedRoute,
    private toastService: ToastService,
    public modalService: NgbModal,
    private titleService: Title,
    private tagService: TagService,
    private correspondentService: CorrespondentService,
    private documentTypeService: DocumentTypeService) { }

  displayMode = 'smallCards' // largeCards, smallCards, details

  filterRules: FilterRule[] = []
  showFilter = false

  tags: PaperlessTag[] = []
  correspondents: PaperlessCorrespondent[] = []
  documentTypes: PaperlessDocumentType[] = []
  filterTagsText: string
  filterCorrespondentsText: string
  filterDocumentTypesText: string

  @ViewChild(FilterEditorComponent) filterEditor;
  
  get isFiltered() {
    return this.list.filterRules?.length > 0
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
        this.filterRules = this.list.filterRules
        this.showFilter = false
        this.titleService.setTitle(`${this.list.savedView.title} - ${environment.appTitle}`)
      } else {
        this.list.savedView = null
        this.filterRules = this.list.filterRules
        this.showFilter = this.filterRules.length > 0
        this.titleService.setTitle(`Documents - ${environment.appTitle}`)
      }
      this.list.clear()
      this.list.reload()
    })
    this.tagService.listAll().subscribe(result => this.tags = result.results)
    this.correspondentService.listAll().subscribe(result => this.correspondents = result.results)
    this.documentTypeService.listAll().subscribe(result => this.documentTypes = result.results)
  }

  applyFilterRules() {
    this.list.filterRules = this.filterRules
  }

  clearFilterRules() {
    this.list.filterRules = this.filterRules
    this.showFilter = false
  }

  loadViewConfig(config: SavedViewConfig) {
    this.filterRules = cloneFilterRules(config.filterRules)
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

  filterByTag(tag_id: number) {
    let filterRules = this.list.filterRules
    if (filterRules.find(rule => rule.type.id == FILTER_HAS_TAG && rule.value == tag_id)) {
      return
    }

    filterRules.push({type: FILTER_RULE_TYPES.find(t => t.id == FILTER_HAS_TAG), value: tag_id})
    this.filterRules = filterRules
    this.applyFilterRules()
  }

  filterByCorrespondent(correspondent_id: number) {
    let filterRules = this.list.filterRules
    let existing_rule = filterRules.find(rule => rule.type.id == FILTER_CORRESPONDENT)
    if (existing_rule && existing_rule.value == correspondent_id) {
      return
    } else if (existing_rule) {
      existing_rule.value = correspondent_id
    } else {
      filterRules.push({type: FILTER_RULE_TYPES.find(t => t.id == FILTER_CORRESPONDENT), value: correspondent_id})
    }
    this.filterRules = filterRules
    this.applyFilterRules()
  }

  filterByDocumentType(document_type_id: number) {
    let filterRules = this.list.filterRules
    let existing_rule = filterRules.find(rule => rule.type.id == FILTER_DOCUMENT_TYPE)
    if (existing_rule && existing_rule.value == document_type_id) {
      return
    } else if (existing_rule) {
      existing_rule.value = document_type_id
    } else {
      filterRules.push({type: FILTER_RULE_TYPES.find(t => t.id == FILTER_DOCUMENT_TYPE), value: document_type_id})
    }
    this.filterRules = filterRules
    this.applyFilterRules()
  }

  findRuleIndex(type_id: number, value: any) {
    return this.list.filterRules.findIndex(rule => rule.type.id == type_id && rule.value == value)
  }

  toggleFilterByTag(tag_id: number) {
    let existingRuleIndex = this.findRuleIndex(FILTER_HAS_TAG, tag_id)
    if (existingRuleIndex !== -1) {
      let filterRules = this.list.filterRules
      filterRules.splice(existingRuleIndex, 1)
      this.filterRules = filterRules
      this.applyFilterRules()
    } else {
      this.filterByTag(tag_id)
    }
  }

  toggleFilterByCorrespondent(correspondent_id: number) {
    let existingRuleIndex = this.findRuleIndex(FILTER_CORRESPONDENT, correspondent_id)
    if (existingRuleIndex !== -1) {
      let filterRules = this.list.filterRules
      filterRules.splice(existingRuleIndex, 1)
      this.filterRules = filterRules
      this.applyFilterRules()
    } else {
      this.filterByCorrespondent(correspondent_id)
    }
  }

  toggleFilterByDocumentType(document_type_id: number) {
    let existingRuleIndex = this.findRuleIndex(FILTER_DOCUMENT_TYPE, document_type_id)
    if (existingRuleIndex !== -1) {
      let filterRules = this.list.filterRules
      filterRules.splice(existingRuleIndex, 1)
      this.filterRules = filterRules
      this.applyFilterRules()
    } else {
      this.filterByDocumentType(document_type_id)
    }
  }

  currentViewIncludesTag(tag_id: number) {
    return this.findRuleIndex(FILTER_HAS_TAG, tag_id) !== -1
  }

  currentViewIncludesCorrespondent(correspondent_id: number) {
    return this.findRuleIndex(FILTER_CORRESPONDENT, correspondent_id) !== -1
  }

  currentViewIncludesDocumentType(document_type_id: number) {
    return this.findRuleIndex(FILTER_DOCUMENT_TYPE, document_type_id) !== -1
  }

  currentViewIncludesQuickFilter() {
    return this.list.filterRules.find(rule => rule.type.id == FILTER_HAS_TAG || rule.type.id == FILTER_CORRESPONDENT || rule.type.id == FILTER_DOCUMENT_TYPE) !== undefined
  }

}
