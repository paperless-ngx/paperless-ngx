import { PaperlessApproval } from "src/app/data/paperless-approval";
import { AbstractPaperlessService } from "./abstract-paperless-service";
import { HttpClient } from "@angular/common/http";
import { DocumentApproval } from "src/app/data/document-approval";
import { Injectable } from "@angular/core";

@Injectable({
  providedIn: 'root',
})
export class ApprovalsService extends AbstractPaperlessService<DocumentApproval> {
  constructor(http: HttpClient) {
    super(http, 'approvals')
  }
}
