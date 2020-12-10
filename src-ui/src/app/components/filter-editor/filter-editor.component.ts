import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { FilterRule } from 'src/app/data/filter-rule';
import { FILTER_CORRESPONDENT, FILTER_DOCUMENT_TYPE, FILTER_HAS_TAG, FILTER_RULE_TYPES } from 'src/app/data/filter-rule-type';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { TagService } from 'src/app/services/rest/tag.service';


@Component({
  selector: 'app-filter-editor',
  templateUrl: './filter-editor.component.html',
  styleUrls: ['./filter-editor.component.scss']
})
export class FilterEditorComponent implements OnInit {

  constructor(private documentTypeService: DocumentTypeService, private tagService: TagService, private correspondentService: CorrespondentService) { }

  @Output()
  clear = new EventEmitter()

  @Input()
  filterRules: FilterRule[] = []

  @Output()
  apply = new EventEmitter()

  correspondents: PaperlessCorrespondent[] = []
  tags: PaperlessTag[] = []
  documentTypes: PaperlessDocumentType[] = []

  filterTagsText: string
  filterCorrespondentsText: string
  filterDocumentTypesText: string

  applySelected() {
    this.apply.next()
  }

  clearSelected() {
    this.filterRules.splice(0,this.filterRules.length)
    this.clear.next()
  }

  hasFilters() {
    return this.filterRules.length > 0
  }

  ngOnInit(): void {
    this.correspondentService.listAll().subscribe(result => {this.correspondents = result.results})
    this.tagService.listAll().subscribe(result => this.tags = result.results)
    this.documentTypeService.listAll().subscribe(result => this.documentTypes = result.results)
  }

  findRuleIndex(type_id: number, value: any) {
    return this.filterRules.findIndex(rule => rule.type.id == type_id && rule.value == value)
  }

  toggleFilterByTag(tag_id: number) {
    let existingRuleIndex = this.findRuleIndex(FILTER_HAS_TAG, tag_id)
    let filterRules = this.filterRules
    if (existingRuleIndex !== -1) {
      filterRules.splice(existingRuleIndex, 1)
    } else {
      filterRules.push({type: FILTER_RULE_TYPES.find(t => t.id == FILTER_HAS_TAG), value: tag_id})
    }
    this.filterRules = filterRules
    this.applySelected()
  }

  toggleFilterByCorrespondent(correspondent_id: number) {
    let filterRules = this.filterRules
    let existingRule = filterRules.find(rule => rule.type.id == FILTER_CORRESPONDENT)
    if (existingRule && existingRule.value == correspondent_id) {
      return
    } else if (existingRule) {
      existingRule.value = correspondent_id
    } else {
      filterRules.push({type: FILTER_RULE_TYPES.find(t => t.id == FILTER_CORRESPONDENT), value: correspondent_id})
    }
    this.filterRules = filterRules
    this.applySelected()
  }

  toggleFilterByDocumentType(document_type_id: number) {
    let filterRules = this.filterRules
    let existingRule = filterRules.find(rule => rule.type.id == FILTER_DOCUMENT_TYPE)
    if (existingRule && existingRule.value == document_type_id) {
      return
    } else if (existingRule) {
      existingRule.value = document_type_id
    } else {
      filterRules.push({type: FILTER_RULE_TYPES.find(t => t.id == FILTER_DOCUMENT_TYPE), value: document_type_id})
    }
    this.filterRules = filterRules
    this.applySelected()
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
    return this.filterRules.find(rule => rule.type.id == FILTER_HAS_TAG || rule.type.id == FILTER_CORRESPONDENT || rule.type.id == FILTER_DOCUMENT_TYPE) !== undefined
  }

}
