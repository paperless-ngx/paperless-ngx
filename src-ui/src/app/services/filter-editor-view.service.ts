import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { TagService } from 'src/app/services/rest/tag.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { FilterRule } from 'src/app/data/filter-rule';
import { FilterRuleType, FILTER_RULE_TYPES, FILTER_CORRESPONDENT, FILTER_DOCUMENT_TYPE, FILTER_HAS_TAG, FILTER_TITLE, FILTER_ADDED_BEFORE, FILTER_ADDED_AFTER, FILTER_CREATED_BEFORE, FILTER_CREATED_AFTER, FILTER_CREATED_YEAR, FILTER_CREATED_MONTH, FILTER_CREATED_DAY } from 'src/app/data/filter-rule-type';
import { Results } from 'src/app/data/results'
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { NgbDate, NgbDateStruct } from '@ng-bootstrap/ng-bootstrap';

@Injectable({
  providedIn: 'root'
})
export class FilterEditorViewService {

  tags: PaperlessTag[] = []
  correspondents: PaperlessCorrespondent[]
  documentTypes: PaperlessDocumentType[] = []

  filterRules: FilterRule[] = []

  constructor(private tagService: TagService, private documentTypeService: DocumentTypeService, private correspondentService: CorrespondentService) {
    this.tagService.listAll().subscribe(result => this.tags = result.results)
    this.correspondentService.listAll().subscribe(result => this.correspondents = result.results)
    this.documentTypeService.listAll().subscribe(result => this.documentTypes = result.results)
  }

  clear() {
    this.filterRules = []
  }

  hasFilters() {
    return this.filterRules.length > 0
  }

  set titleFilter(title: string) {
    let existingRule = this.filterRules.find(rule => rule.type.id == FILTER_TITLE)

    if (!existingRule && title) {
      this.filterRules.push({type: FILTER_RULE_TYPES.find(t => t.id == FILTER_TITLE), value: title})
    } else if (existingRule && !title) {
      this.filterRules.splice(this.filterRules.findIndex(rule => rule.type.id == FILTER_TITLE), 1)
    } else if (existingRule && title) {
      existingRule.value = title
    }
  }

  get titleFilter(): string {
    let existingRule = this.filterRules.find(rule => rule.type.id == FILTER_TITLE)
    return existingRule ? existingRule.value : ''
  }

  get selectedTags(): PaperlessTag[] {
    let tagRules: FilterRule[] = this.filterRules.filter(fr => fr.type.id == FILTER_HAS_TAG)
    return this.tags?.filter(t => tagRules.find(tr => tr.value == t.id))
  }

  get selectedCorrespondents(): PaperlessCorrespondent[] {
    let correspondentRules: FilterRule[] = this.filterRules.filter(fr => fr.type.id == FILTER_CORRESPONDENT)
    return this.correspondents?.filter(c => correspondentRules.find(cr => cr.value == c.id))
  }

  get selectedDocumentTypes(): PaperlessDocumentType[] {
    let documentTypeRules: FilterRule[] = this.filterRules.filter(fr => fr.type.id == FILTER_DOCUMENT_TYPE)
    return this.documentTypes?.filter(dt => documentTypeRules.find(dtr => dtr.value == dt.id))
  }

  toggleFilterByTag(tag: PaperlessTag | number) {
    if (typeof tag == 'number') tag = this.tags?.find(t => t.id == tag)
    this.toggleFilterByItem(tag, FILTER_HAS_TAG)
  }

  toggleFilterByCorrespondent(correspondent: PaperlessCorrespondent | number) {
    if (typeof correspondent == 'number') correspondent = this.correspondents?.find(t => t.id == correspondent)
    this.toggleFilterByItem(correspondent, FILTER_CORRESPONDENT)
  }

  toggleFilterByDocumentType(documentType: PaperlessDocumentType | number) {
    if (typeof documentType == 'number') documentType = this.documentTypes?.find(t => t.id == documentType)
    this.toggleFilterByItem(documentType, FILTER_DOCUMENT_TYPE)
  }

  private toggleFilterByItem(item: ObjectWithId, filterRuleTypeID: number) {
    let filterRules = this.filterRules
    let filterRuleType: FilterRuleType = FILTER_RULE_TYPES.find(t => t.id == filterRuleTypeID)
    let existingRules = filterRules.filter(rule => rule.type.id == filterRuleType.id)
    let existingItemRule = existingRules?.find(rule => rule.value == item.id)

    if (existingRules && existingItemRule) { // if exact rule exists just remove
      filterRules.splice(filterRules.indexOf(existingItemRule), 1)
    } else if (existingRules.length > 0 && filterRuleType.multi) { // e.g. tags can have multiple
      filterRules.push({type: filterRuleType, value: item.id})
    } else if (existingRules.length > 0) { // correspondents & documentTypes can only be one
      filterRules.find(rule => rule.type.id == filterRuleType.id).value = item.id
    } else {
      filterRules.push({type: filterRuleType, value: item.id})
    }

    this.filterRules = filterRules
  }

  get dateCreatedBefore(): NgbDateStruct {
    let createdBeforeRule: FilterRule = this.filterRules.find(fr => fr.type.id == FILTER_CREATED_BEFORE)
    return createdBeforeRule ? {
      year: createdBeforeRule.value.substring(0,4),
      month: createdBeforeRule.value.substring(5,7),
      day: createdBeforeRule.value.substring(8,10)
    } : undefined
  }

  get dateCreatedAfter(): NgbDateStruct {
    let createdAfterRule: FilterRule = this.filterRules.find(fr => fr.type.id == FILTER_CREATED_AFTER)
    return createdAfterRule ? {
      year: createdAfterRule.value.substring(0,4),
      month: createdAfterRule.value.substring(5,7),
      day: createdAfterRule.value.substring(8,10)
    } : undefined
  }

  get dateAddedBefore(): NgbDateStruct {
    let addedBeforeRule: FilterRule = this.filterRules.find(fr => fr.type.id == FILTER_ADDED_BEFORE)
    return addedBeforeRule ? {
      year: addedBeforeRule.value.substring(0,4),
      month: addedBeforeRule.value.substring(5,7),
      day: addedBeforeRule.value.substring(8,10)
    } : undefined
  }

  get dateAddedAfter(): NgbDateStruct {
    let addedAfterRule: FilterRule = this.filterRules.find(fr => fr.type.id == FILTER_ADDED_AFTER)
    return addedAfterRule ? {
      year: addedAfterRule.value.substring(0,4),
      month: addedAfterRule.value.substring(5,7),
      day: addedAfterRule.value.substring(8,10)
    } : undefined
  }

  setDateCreatedBefore(date?: NgbDateStruct) {
    if (date) this.setDateFilter(date, FILTER_CREATED_BEFORE)
    else this.clearDateFilter(FILTER_CREATED_BEFORE)
  }

  setDateCreatedAfter(date?: NgbDateStruct) {
    if (date) this.setDateFilter(date, FILTER_CREATED_AFTER)
    else this.clearDateFilter(FILTER_CREATED_AFTER)
  }

  setDateAddedBefore(date?: NgbDateStruct) {
    if (date) this.setDateFilter(date, FILTER_ADDED_BEFORE)
    else this.clearDateFilter(FILTER_ADDED_BEFORE)
  }

  setDateAddedAfter(date?: NgbDateStruct) {
    if (date) this.setDateFilter(date, FILTER_ADDED_AFTER)
    else this.clearDateFilter(FILTER_ADDED_AFTER)
  }

  setDateFilter(date: NgbDateStruct, dateRuleTypeID: number) {
    let filterRules = this.filterRules
    let existingRule = filterRules.find(rule => rule.type.id == dateRuleTypeID)
    let newValue = `${date.year}-${date.month.toString().padStart(2,'0')}-${date.day.toString().padStart(2,'0')}` // YYYY-MM-DD

    if (existingRule) {
      existingRule.value = newValue
    } else {
      filterRules.push({type: FILTER_RULE_TYPES.find(t => t.id == dateRuleTypeID), value: newValue})
    }

    this.filterRules = filterRules
  }

  clearDateFilter(dateRuleTypeID: number) {
    let filterRules = this.filterRules
    let existingRule = filterRules.find(rule => rule.type.id == dateRuleTypeID)
    filterRules.splice(filterRules.indexOf(existingRule), 1)
    this.filterRules = filterRules
  }
}
