import { Approval } from "src/app/data/approval";
import { AbstractEdocService } from "./abstract-edoc-service";
import { HttpClient } from "@angular/common/http";
import { DocumentApproval } from "src/app/data/document-approval";
import { Injectable } from "@angular/core";

@Injectable({
  providedIn: 'root',
})
export class ApprovalsService extends AbstractEdocService<DocumentApproval> {
  constructor(http: HttpClient) {
    super(http, 'approvals')
  }
}
