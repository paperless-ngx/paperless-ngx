import { Component, EventEmitter, Input, OnInit, Output } from '@angular/core';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { TagService } from 'src/app/services/rest/tag.service';

export interface FilterRuleType {
  name: string
  filtervar: string
  datatype: string //number, string, boolean, date
}

export interface FilterRule {
  type: FilterRuleType
  value: any
}

export class FilterRuleSet {

  static RULE_TYPES: FilterRuleType[] = [
    {name: "Title contains", filtervar: "title__icontains", datatype: "string"},
    {name: "Content contains", filtervar: "content__icontains", datatype: "string"},
    
    {name: "ASN is", filtervar: "archive_serial_number", datatype: "number"},
    
    {name: "Correspondent is", filtervar: "correspondent__id", datatype: "correspondent"},
    {name: "Document type is", filtervar: "document_type__id", datatype: "document_type"},
    {name: "Has tag", filtervar: "tags__id", datatype: "tag"},
    
    {name: "Has any tag", filtervar: "is_tagged", datatype: "boolean"},
  
    {name: "Date created before", filtervar: "created__date__lt", datatype: "date"},
    {name: "Date created after", filtervar: "created__date__gt", datatype: "date"},
  
    {name: "Year created is", filtervar: "created__year", datatype: "number"},
    {name: "Month created is", filtervar: "created__month", datatype: "number"},
    {name: "Day created is", filtervar: "created__day", datatype: "number"},
  
    {name: "Date added before", filtervar: "added__date__lt", datatype: "date"},
    {name: "Date added after", filtervar: "added__date__gt", datatype: "date"},
    
    {name: "Date modified before", filtervar: "modified__date__lt", datatype: "date"},
    {name: "Date modified after", filtervar: "modified__date__gt", datatype: "date"},
  ]

  rules: FilterRule[] = []

  toQueryParams() {
    let params = {}
    for (let rule of this.rules) {
      params[rule.type.filtervar] = rule.value
    }
    return params
  }

  clone(): FilterRuleSet {
    let newRuleSet = new FilterRuleSet()
    for (let rule of this.rules) {
      newRuleSet.rules.push({type: rule.type, value: rule.value})
    }
    return newRuleSet
  }

  constructor() { }

}

@Component({
  selector: 'app-filter-editor',
  templateUrl: './filter-editor.component.html',
  styleUrls: ['./filter-editor.component.css']
})
export class FilterEditorComponent implements OnInit {

  constructor(private documentTypeService: DocumentTypeService, private tagService: TagService, private correspondentService: CorrespondentService) { }

  @Input()
  ruleSet = new FilterRuleSet()

  @Output()
  ruleSetChange = new EventEmitter<FilterRuleSet>()

  @Output()
  apply = new EventEmitter()

  selectedRuleType: FilterRuleType = FilterRuleSet.RULE_TYPES[0]

  correspondents: PaperlessCorrespondent[] = []
  tags: PaperlessTag[] = []
  documentTypes: PaperlessDocumentType[] = []

  newRuleClicked() {
    this.ruleSet.rules.push({type: this.selectedRuleType, value: null})
  }

  removeRuleClicked(rule) {
    let index = this.ruleSet.rules.findIndex(r => r == rule)
    if (index > -1) {
      this.ruleSet.rules.splice(index, 1)
    }
  }

  applyClicked() {
    this.apply.next()
  }

  ngOnInit(): void {
    this.correspondentService.list().subscribe(result => {this.correspondents = result.results})
    this.tagService.list().subscribe(result => this.tags = result.results)
    this.documentTypeService.list().subscribe(result => this.documentTypes = result.results)
  }

  getRuleTypes() {
    return FilterRuleSet.RULE_TYPES
  }
}
