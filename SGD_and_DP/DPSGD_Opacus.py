from data.fed_data_distribution.pathological_nonIID_data import pathological_split_noniid
from data.get_data import get_data
from data.util.sampling import get_data_loaders_uniform_without_replace
from model.CNN import CNN_tanh, CNN
from model.ResNet import resnet20
from optimizer.dp_optimizer import DPSGD, DPAdam
import torch
from torch import nn
from torch.utils.data import TensorDataset
from torch.utils.data import DataLoader

from privacy_analysis.RDP.compute_rdp import compute_rdp
from privacy_analysis.RDP.rdp_convert_dp import compute_eps
from train_and_validation.train import train
from train_and_validation.train_with_dp import  train_dynamic_add_noise
from train_and_validation.validation import validation
from openpyxl import Workbook
import time

from opacus import PrivacyEngine


def centralization_train_with_dp_by_opacus(train_data, test_data, model,batch_size, numEpoch, learning_rate,momentum,delta,max_norm,sigma):


    optimizer = torch.optim.SGD(model.parameters(), lr=learning_rate)
    centralized_criterion = nn.CrossEntropyLoss()

    # 包装抽样函数
    minibatch_size = batch_size  # 这里比较好的取值是根号n，n为每个客户端的样本数
    microbatch_size = 1  #这里默认1就好
    iterations = 1  # n个batch，这边就定一个，每次训练采样一个Lot
    minibatch_loader, microbatch_loader = get_data_loaders_uniform_without_replace(minibatch_size, microbatch_size, iterations)     #无放回均匀采样

    # Dataset是一个包装类，用来将数据包装为Dataset类，然后传入DataLoader中，我们再使用DataLoader这个类来更加快捷的对数据进行操作。
    # DataLoader是一个比较重要的类，它为我们提供的常用操作有：batch_size(每个batch的大小), shuffle(是否进行shuffle操作)
    # DataLoader里的数据要通过for i ,data in enumerate(DataLoader)才能打印出来

    train_dl = torch.utils.data.DataLoader(
        train_data, batch_size=batch_size, shuffle=True)

    #train数据在下面进行采样，这边不做dataloader
    test_dl = torch.utils.data.DataLoader(
        test_data, batch_size=batch_size, shuffle=False)

    print("------ Centralized Model ------")
    rdp=0
    orders = (list(range(2, 64)) + [128, 256, 512])  # 默认的lamda
    epsilon_list=[]
    result_loss_list=[]
    result_acc_list=[]

    privacy_engine = PrivacyEngine()
    #privacy_engine = PrivacyEngine(secure_mode ="False")
    model_opacus, optimizer_opacus, train_dl_opacus = privacy_engine.make_private(
        module=model,
        optimizer=optimizer,
        data_loader=train_dl,
        noise_multiplier=sigma,
        max_grad_norm=max_norm,
    )


    for epoch in range(numEpoch):

       # print("model:",model.state_dict())
       # train_dl = minibatch_loader(train_data)     #抽样
       #这里要动态加噪，每次传入的sigma可能会改变
        central_train_loss, central_train_accuracy = train(model_opacus, train_dl_opacus, centralized_criterion, optimizer_opacus)
        central_test_loss, central_test_accuracy = validation(model_opacus, test_dl)

        # 这里要每次根据simga累加它的RDP，循环结束再转为eps，这里的epoch系数直接设为iterations(epoch里的迭代次数)，每次算一轮累和
        rdp_every_epoch=compute_rdp(batch_size/len(train_data), sigma, 1*iterations, orders)
        rdp=rdp+rdp_every_epoch
        epsilon, best_alpha = compute_eps(orders, rdp, delta)
        epsilon_list.append(epsilon)

        result_loss_list.append(central_test_loss)
        result_acc_list.append(central_test_accuracy)

        print("epoch: {:3.0f}".format(epoch + 1) + " | epsilon: {:7.4f}".format(
        epsilon) + " | best_alpha: {:7.4f}".format(best_alpha)  )


    print("------ Training finished ------")

if __name__=="__main__":

    train_data, test_data = get_data('cifar10', augment=False)
   #  print(train_data.__dict__)
   #  model = CNN()
    model= resnet20(10, False)
    batch_size = 256
    learning_rate = 0.01
    numEpoch = 1500
    sigma = 0.000001
    momentum = 0.9
    delta = 10 ** (-5)
    max_norm =100
    centralization_train_with_dp_by_opacus(train_data, test_data, model,batch_size, numEpoch, learning_rate,momentum,delta,max_norm,sigma)