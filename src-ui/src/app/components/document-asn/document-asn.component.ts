import { Component, OnInit, inject } from '@angular/core'
import { ActivatedRoute, Router } from '@angular/router'
import { FILTER_ASN } from '../../data/filter-rule-type'
import { DocumentService } from '../../services/rest/document.service'

@Component({
  selector: 'pngx-document-asncomponent',
  templateUrl: './document-asn.component.html',
  styleUrls: ['./document-asn.component.scss'],
})
export class DocumentAsnComponent implements OnInit {
  private documentsService = inject(DocumentService)
  private route = inject(ActivatedRoute)
  private router = inject(Router)

  asn: string

  ngOnInit(): void {
    this.route.paramMap.subscribe((paramMap) => {
      this.asn = paramMap.get('id')
      this.documentsService
        .listAllFilteredIds([{ rule_type: FILTER_ASN, value: this.asn }])
        .subscribe((documentId) => {
          if (documentId.length == 1) {
            this.router.navigate(['documents', documentId[0]])
          } else {
            this.router.navigate(['404'], {
              replaceUrl: true,
            })
          }
        })
    })
  }
}
