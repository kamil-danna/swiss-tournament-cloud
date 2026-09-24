terraform {
  required_version = ">= 1.0.0"
}

# Creazione della macchina virtuale per Kubernetes tramite Multipass
resource "null_resource" "k8s_node" {
  provisioner "local-exec" {
    # Usiamo multipass.exe perché il demone risiede su Windows
    command = "multipass.exe launch 22.04 --name k8s-cluster --cpus 2 --memory 4G --disk 10G"
  }

  provisioner "local-exec" {
    when    = destroy
    command = "multipass.exe delete --purge k8s-cluster"
  }
}   