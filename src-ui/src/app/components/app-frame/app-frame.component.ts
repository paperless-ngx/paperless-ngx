import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormControl } from '@angular/forms';
import { Router } from '@angular/router';
import { Subscription } from 'rxjs';
import { PaperlessDocument } from 'src/app/data/paperless-document';
import { AuthService } from 'src/app/services/auth.service';
import { OpenDocumentsService } from 'src/app/services/open-documents.service';

@Component({
  selector: 'app-app-frame',
  templateUrl: './app-frame.component.html',
  styleUrls: ['./app-frame.component.css']
})
export class AppFrameComponent implements OnInit, OnDestroy {

  constructor (public router: Router, private openDocumentsService: OpenDocumentsService, private authService: AuthService) {
  }

  searchField = new FormControl('')

  openDocuments: PaperlessDocument[] = []

  openDocumentsSubscription: Subscription

  search() {
    this.router.navigate(['search'], {queryParams: {query: this.searchField.value}})
  }

  logout() {
    this.authService.logout()
  }

  ngOnInit() {
    this.openDocumentsSubscription = this.openDocumentsService.getOpenDocuments().subscribe(docs => this.openDocuments = docs)
  }

  ngOnDestroy() {
    this.openDocumentsSubscription.unsubscribe()
  }

}
