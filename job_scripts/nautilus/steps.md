# Storage

Define storage with:

```bash
kubectl create -f k8s\pvc.yaml
```

# Jobs

Run jobs using
```bash
python orchestrate.py --seed 0
```
the log files will be saved locally

# See files

Use the following command to get a cmd into the PVC
```bash
kubectl apply -f pvc-browser.yaml
kubectl exec -it pvc-browser -n design-reasoning-lab -- sh
```

And when done
```bash
kubectl delete pod pvc-browser -n design-reasoning-lab
```

# Download files

Use
```bash
# Copy a single file
kubectl cp design-reasoning-lab/pvc-browser:/mnt/results/1234567890/g0/evaluation.csv ./evaluation.csv

# Copy a whole directory
kubectl cp design-reasoning-lab/pvc-browser:/mnt/results/1234567890 ./results
```
whie the above command for viewing files is running and keeping pvc-browser alive